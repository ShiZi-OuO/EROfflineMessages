#include "MessagePack.h"
#include <iostream>
int main(int argc,char** argv){
    if(argc!=2){std::cerr<<"Usage: er_pack_check pack.json\n";return 2;}
    try{
        auto pack=er::MessagePack::Load(argv[1]);size_t maximum{};
        for(const auto& [map,entries]:pack.byMap){(void)map;if(entries.size()>maximum)maximum=entries.size();}
        // Spatial replay caps each nearby selection at 96. A map may contain
        // more records; its total is not the simultaneously registered count.
        std::cout<<"source="<<pack.source<<" records="<<pack.messages.size()<<" maps="<<pack.byMap.size()<<" maximum_per_map="<<maximum<<" nearby_selection_limit=96\n";
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
