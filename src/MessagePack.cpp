#include "MessagePack.h"
#include <json.hpp>
#include <charconv>
#include <cmath>
#include <cstring>
#include <fstream>
#include <set>
#include <stdexcept>

namespace er {
namespace {
using Json=nlohmann::json;
void Require(bool condition,const char* reason){if(!condition)throw std::runtime_error(reason);}
void Keys(const Json& object,std::initializer_list<const char*> allowed){
    Require(object.is_object(),"Expected object");
    for(auto it=object.begin();it!=object.end();++it){bool ok=false;for(auto key:allowed)if(it.key()==key)ok=true;Require(ok,"Unknown field: only anonymous semantic fields are allowed");}
}
uint64_t Unsigned(const Json& value,uint64_t maximum){
    Require(value.is_number_unsigned()||(value.is_number_integer()&&value.get<int64_t>()>=0),"Expected unsigned integer");
    auto v=value.get<uint64_t>();Require(v<=maximum,"Integer out of range");return v;
}
float Finite(const Json& value){Require(value.is_number(),"Expected coordinate number");auto v=value.get<double>();Require(std::isfinite(v)&&std::abs(v)<=1000000,"Invalid or unbounded coordinate");return static_cast<float>(v);}
template<class T>void Store(std::span<uint8_t,PayloadSize> bytes,size_t offset,const T& value)noexcept{std::memcpy(bytes.data()+offset,&value,sizeof(value));}
}
MessagePack MessagePack::Parse(const std::string& text){
    Require(text.size()<=32*1024*1024,"Data file size budget exceeded");
    auto root=Json::parse(text);Keys(root,{"schema_version","game","source_type","description","messages"});
    Require(Unsigned(root.at("schema_version"),1)==1,"Unsupported schema version");
    Require(root.at("game")=="eldenring","Wrong game");
    MessagePack pack;pack.source=root.at("source_type").get<std::string>();
    Require(pack.source=="constructed"||pack.source=="official_client_sample"
        ||pack.source=="official_protocol_sample"||pack.source=="official_sample","Unknown provenance");
    const auto& records=root.at("messages");Require(records.is_array()&&records.size()<=100000,"Message count budget exceeded");
    std::set<uint64_t> ids;
    for(const auto& r:records){
        Keys(r,{"id","map","area","secondary_area","position","yaw","template1","word1","conjunction","template2","word2","good","poor"});
        Message m;auto id=r.at("id").get<std::string>();Require(id.size()==16,"Local ID must be 16 hex digits");
        auto parsed=std::from_chars(id.data(),id.data()+id.size(),m.id,16);
        Require(parsed.ec==std::errc{}&&parsed.ptr==id.data()+id.size(),"Invalid local ID");
        Require((m.id>>56)==(pack.source=="constructed"?0x7e:0x7d),"Local ID provenance namespace mismatch");
        Require(ids.insert(m.id).second,"Duplicate local ID");
        m.map=static_cast<uint32_t>(Unsigned(r.at("map"),UINT32_MAX-1));Require(m.map!=0,"Map required");
        m.area=static_cast<uint32_t>(Unsigned(r.at("area"),UINT32_MAX));Require(m.area!=0,"Area required");
        m.secondaryArea=static_cast<uint32_t>(Unsigned(r.value("secondary_area",Json(0)),UINT32_MAX));
        const auto& pos=r.at("position");Require(pos.is_array()&&pos.size()==3,"Position needs three values");
        for(size_t i=0;i<3;++i)m.position[i]=Finite(pos[i]);m.yaw=Finite(r.at("yaw"));
        m.template1=static_cast<uint16_t>(Unsigned(r.at("template1"),UINT16_MAX));Require(m.template1!=0,"First phrase required");
        m.word1=static_cast<uint16_t>(Unsigned(r.at("word1"),UINT16_MAX));
        m.conjunction=static_cast<uint16_t>(Unsigned(r.at("conjunction"),UINT16_MAX));
        m.template2=static_cast<uint16_t>(Unsigned(r.at("template2"),UINT16_MAX));
        m.word2=static_cast<uint16_t>(Unsigned(r.at("word2"),UINT16_MAX));
        Require(m.template2!=0||(m.word2==0&&m.conjunction==0),"Incomplete second phrase");
        m.good=static_cast<uint16_t>(Unsigned(r.at("good"),9999));m.poor=static_cast<uint16_t>(Unsigned(r.at("poor"),9999));
        pack.byMap[m.map].push_back(pack.messages.size());pack.messages.push_back(m);
    }
    return pack;
}
MessagePack MessagePack::Load(const std::filesystem::path& path){
    Require(std::filesystem::file_size(path)<=32*1024*1024,"Data file size budget exceeded");
    std::ifstream file(path,std::ios::binary);Require(file.good(),"Cannot open message data");
    std::string text((std::istreambuf_iterator<char>(file)),{});return Parse(text);
}
void Message::WriteFields(std::span<uint8_t,PayloadSize> payload)const noexcept{
    // Call the verified native neutral appearance initializer before writing semantics.
    const uint32_t localSender=0x7e000001;Store(payload,0x1b4,localSender);
    Store(payload,0x1b8,id);Store(payload,0x1c0,map);Store(payload,0x1c4,secondaryArea);
    Store(payload,0x1c8,position);Store(payload,0x1d4,yaw);
    // Native creation constructor initializes gesture byte to 0xff (none), not gesture 0.
    const uint16_t gesture=0xff;Store(payload,0x1d8,template1);Store(payload,0x1da,gesture);
    Store(payload,0x1dc,word1);Store(payload,0x1de,conjunction);Store(payload,0x1e0,template2);Store(payload,0x1e2,word2);
    Store(payload,0x1e4,good);Store(payload,0x1e6,poor);
    Store(payload,0x1f0,id);Store(payload,0x1f8,area);
}
}
