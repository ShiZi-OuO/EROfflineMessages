#include "SpatialIndex.h"
#include <algorithm>
#include <cmath>
#include <functional>
#include <stdexcept>

namespace er {
int SpatialIndex::Build(std::vector<size_t>& items,size_t first,size_t last,unsigned depth){
    if(first==last)return -1;
    const auto axis=depth%3;const auto mid=first+(last-first)/2;
    std::nth_element(items.begin()+first,items.begin()+mid,items.begin()+last,[&](auto a,auto b){
        const auto x=pack.messages[a].position[axis],y=pack.messages[b].position[axis];
        return x!=y?x<y:pack.messages[a].id<pack.messages[b].id;
    });
    const auto slot=static_cast<int>(nodes.size());nodes.push_back({items[mid],-1,-1,axis});
    const auto left=Build(items,first,mid,depth+1),right=Build(items,mid+1,last,depth+1);
    nodes[slot].left=left;nodes[slot].right=right;return slot;
}
SpatialIndex::SpatialIndex(const MessagePack& data):pack(data){
    nodes.reserve(pack.messages.size());
    for(const auto& [map,records]:pack.byMap){auto items=records;roots.emplace(map,Build(items,0,items.size(),0));}
}
SpatialResult SpatialIndex::Nearby(uint32_t map,const std::array<float,3>& position,
                                    double radius,size_t maximum,size_t budget)const{
    if(!std::isfinite(radius)||radius<=0||radius>10000||maximum>96||budget>16384
       ||std::any_of(position.begin(),position.end(),[](float x){return !std::isfinite(x)||std::abs(x)>1000000;}))
        throw std::invalid_argument("Spatial query bounds");
    SpatialResult result;const auto root=roots.find(map);
    if(root==roots.end()||!maximum)return result;
    struct Candidate {double distance;uint64_t key;size_t index;
        bool operator<(const Candidate& b)const{return distance!=b.distance?distance<b.distance:key<b.key;}};
    std::priority_queue<Candidate> nearest;const auto radius2=radius*radius;
    std::function<void(int)> visit=[&](int slot){
        if(slot<0)return;
        if(result.visited==budget){result.budgetExhausted=true;return;}
        ++result.visited;const auto& node=nodes[slot];const auto& record=pack.messages[node.record];
        double distance=0;for(unsigned k=0;k<3;++k){const auto d=static_cast<double>(record.position[k])-position[k];distance+=d*d;}
        Candidate candidate{distance,record.id,node.record};
        if(distance<=radius2){
            if(nearest.size()<maximum)nearest.push(candidate);
            else if(candidate<nearest.top()){nearest.pop();nearest.push(candidate);}
        }
        const auto delta=static_cast<double>(position[node.axis])-record.position[node.axis];
        visit(delta<0?node.left:node.right);
        const auto threshold=nearest.size()==maximum?std::min(radius2,nearest.top().distance):radius2;
        if(delta*delta<=threshold)visit(delta<0?node.right:node.left);
    };
    visit(root->second);
    while(!nearest.empty()){result.indices.push_back(nearest.top().index);nearest.pop();}
    std::reverse(result.indices.begin(),result.indices.end());return result;
}
}
