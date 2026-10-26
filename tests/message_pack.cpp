#include "MessagePack.h"
#include <json.hpp>
#include <cstring>
#include <iostream>
#include <stdexcept>

using J=nlohmann::json;
void Check(bool c,const char* reason){if(!c)throw std::runtime_error(reason);}
void Rejected(const J& j){try{er::MessagePack::Parse(j.dump());}catch(...){return;}throw std::runtime_error("Invalid data accepted");}
int main(){try{
    J record={{"id","7e00000000000001"},{"map",0x3c2a2400},{"area",600000},{"position",{1,2,3}},{"yaw",0},{"template1",10000},{"word1",20000},{"conjunction",0},{"template2",0},{"word2",0},{"good",7},{"poor",3}};
    J pack={{"schema_version",1},{"game","eldenring"},{"source_type","constructed"},{"messages",J::array({record})}};
    auto good=er::MessagePack::Parse(pack.dump());Check(good.messages.size()==1&&good.byMap.at(0x3c2a2400).size()==1,"map index");
    auto x=pack;x["messages"].push_back(record);Rejected(x);
    x=pack;x["messages"][0]["position"]={1,2};Rejected(x);
    x=pack;x["messages"][0]["position"][0]=1e30;Rejected(x);
    x=pack;x["messages"][0]["map"]=-1;Rejected(x);
    x=pack;x["messages"][0]["template1"]=65536;Rejected(x);
    x=pack;x["messages"][0]["good"]=10000;Rejected(x);
    x=pack;x["messages"][0]["player_id"]=123;Rejected(x);
    x=pack;x["messages"][0]["id"]="7e0000000000000z";Rejected(x);
    x=pack;x["source_type"]="official_client_sample";Rejected(x);
    x=pack;x["source_type"]="official_protocol_sample";x["messages"][0]["id"]="7d00000000000001";
    Check(er::MessagePack::Parse(x.dump()).source=="official_protocol_sample","Protocol origin lost");
    x["source_type"]="official_sample";Check(er::MessagePack::Parse(x.dump()).messages.size()==1,"Mixed official origin rejected");
    x=pack;x["messages"][0]["word2"]=20000;Rejected(x);
    x=pack;x["schema_version"]=2;Rejected(x);
    std::array<uint8_t,er::PayloadSize> bytes;bytes.fill(0xa5);good.messages[0].WriteFields(bytes);
    for(size_t i=0;i<0x1b4;++i)Check(bytes[i]==0xa5,"appearance/name overwritten");
    uint64_t id{};std::memcpy(&id,bytes.data()+0x1f0,8);Check(id==good.messages[0].id,"native key");
    uint16_t ratings[2]{};std::memcpy(ratings,bytes.data()+0x1e4,4);Check(ratings[0]==7&&ratings[1]==3,"rating fields");
    Check(bytes[0x1da]==0xff&&bytes[0x1db]==0,"gesture disabled");
    std::cout<<"PASS: provenance, privacy allowlist, duplicate keys, numeric bounds, index and payload boundaries\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
