"""Narrow, independently implemented primitive encoding for the exact-image pilot.

No sockets, credentials or game access. Only session creation and read-only
message-list request variants are exposed. Numeric layout checked against local
native writer RVAs 1e3e360, 1e38200/1e38350/1e38360/1e38130.
"""
import struct


def blob(value):
    if not isinstance(value, bytes) or len(value) > 1048576:
        raise ValueError('Bounded binary value required')
    return struct.pack('<I', len(value))+value


def create_session(sequence, magic, version, ticket, platform=0, region=0,
                   language=0, cross_region=False, flags=False, text=b'', tail=(0,0,0,0)):
    if len(magic)!=3 or len(tail)!=4 or not 0<len(ticket)<=4096:
        raise ValueError('Session field shape')
    # Steam ticket is variant 1, containing a byte vector. No identity headers.
    return (struct.pack('<BII3IQI',4,sequence,0,*magic,version,1)+blob(ticket)
            +struct.pack('<IBIIB',platform,bool(cross_region),region,language,bool(flags))
            +blob(text)+struct.pack('<4I',*tail))


def message_list(sequence, areas):
    if not 1<=len(areas)<=8 or len(set(areas))!=len(areas):
        raise ValueError('One bounded set of unique search area pairs required')
    if any(type(v) is not int or not 0<v<0xffffffff for pair in areas for v in pair) or any(len(p)!=2 for p in areas):
        raise ValueError('Invalid search area pair')
    # Native request variant 18; empty group-password vector.
    return struct.pack('<BIII',4,sequence,18,len(areas))+b''.join(struct.pack('<II',*p) for p in areas)+struct.pack('<I',0)


class Cursor:
    def __init__(self,data):
        if not isinstance(data,bytes) or len(data)>16*1024*1024:raise ValueError('Wire buffer budget')
        self.data=data;self.offset=0
    def take(self,n):
        if n<0 or self.offset+n>len(self.data):raise ValueError('Truncated wire field')
        v=self.data[self.offset:self.offset+n];self.offset+=n;return v
    def number(self,fmt):return struct.unpack('<'+fmt,self.take(struct.calcsize('<'+fmt)))[0]
    def vector(self,maximum=1048576):
        n=self.number('I')
        if n>maximum:raise ValueError('Length field budget')
        return self.take(n)


def response_header(data,sequence,variant):
    r=Cursor(data)
    if r.number('B')!=5 or r.number('I')!=sequence:raise ValueError('Unexpected response sequence/type')
    success=r.number('B')
    if success==0:raise RuntimeError('Official RPC error '+str(r.number('I')))
    if success!=1 or r.number('I')!=variant:raise ValueError('Unexpected response variant')
    return r
