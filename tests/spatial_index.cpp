#include "SpatialIndex.h"
#include <iostream>
#include <stdexcept>

void Require(bool condition,const char* reason){if(!condition)throw std::runtime_error(reason);}
int main(){
    try{
        er::MessagePack pack;
        for(size_t i=0;i<10000;++i){er::Message m;m.id=i+1;m.map=1;m.position={static_cast<float>(i*2),0,0};
            pack.byMap[1].push_back(i);pack.messages.push_back(m);}
        er::Message other;other.id=10001;other.map=2;other.position={19998,0,0};
        pack.byMap[2].push_back(pack.messages.size());pack.messages.push_back(other);
        er::SpatialIndex index(pack);
        auto result=index.Nearby(1,{19998,0,0},20);
        Require(result.indices.size()==11,"Radius boundary lost");
        Require(result.indices.front()==9999,"Distant data omitted by pack-prefix selection");
        Require(result.visited<=2048&&!result.budgetExhausted,"Sparse query budget exhausted");
        for(auto n:result.indices)Require(pack.messages[n].map==1,"Other map leaked into selection");
        Require(index.Nearby(9,{0,0,0},100).indices.empty(),"Unknown map returned data");
        er::MessagePack dense;
        for(size_t i=0;i<10000;++i){er::Message m;m.id=i+1;m.map=1;m.position={0,0,0};
            dense.byMap[1].push_back(i);dense.messages.push_back(m);}
        auto bounded=er::SpatialIndex(dense).Nearby(1,{0,0,0},100,96,256);
        Require(bounded.indices.size()<=96&&bounded.visited==256&&bounded.budgetExhausted,"Dense query not bounded");
        bool rejected=false;try{index.Nearby(1,{0,0,0},-1);}catch(const std::invalid_argument&){rejected=true;}
        Require(rejected,"Invalid radius accepted");
        std::cout<<"Spatial candidate tests passed; no game verification implied\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
