#pragma once
#include "MessagePack.h"
#include <queue>

namespace er {
struct SpatialResult {
    std::vector<size_t> indices;
    size_t visited{};
    bool budgetExhausted{};
};
// Connected to the 0.1.4 development DLL; 0.1.3 is the frozen tested baseline.
// All input/query coordinates must be native block-local coordinates.
class SpatialIndex {
    struct Node {size_t record{};int left{-1},right{-1};unsigned axis{};};
    const MessagePack& pack;
    std::vector<Node> nodes;
    std::unordered_map<uint32_t,int> roots;
    int Build(std::vector<size_t>&,size_t,size_t,unsigned);
public:
    explicit SpatialIndex(const MessagePack&);
    SpatialResult Nearby(uint32_t map,const std::array<float,3>& blockPosition,
                         double radius,size_t maximum=96,size_t visitBudget=2048)const;
};
}
