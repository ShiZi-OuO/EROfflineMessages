#pragma once
#include <algorithm>
#include <cstddef>
#include <limits>
#include <span>

namespace er {
struct CacheResident {
    size_t record=std::numeric_limits<size_t>::max();
    bool protectedFromRetirement{};
};
// Preserve every foreign object and every protected own object outside the
// chosen prefix. Only our unprotected unselected objects can be retired by
// the native lifecycle. Never evict or change a display binding here.
inline size_t CachePrefix(std::span<const size_t> candidates,
                          std::span<const CacheResident> residents,
                          size_t capacity,size_t reserve=8) {
    const auto foreign=static_cast<size_t>(std::count_if(residents.begin(),residents.end(),
        [](const auto& r){return r.record==std::numeric_limits<size_t>::max();}));
    const auto protectedOwn=static_cast<size_t>(std::count_if(residents.begin(),residents.end(),
        [](const auto& r){return r.record!=std::numeric_limits<size_t>::max()&&r.protectedFromRetirement;}));
    const auto ceiling=capacity>reserve?capacity-reserve:0;
    size_t selectedProtected{},accepted{};
    for(size_t i=0;i<candidates.size();++i){
        if(std::any_of(residents.begin(),residents.end(),[&](const auto& r){
            return r.record==candidates[i]&&r.protectedFromRetirement;
        }))++selectedProtected;
        if(foreign+protectedOwn-selectedProtected+i+1<=ceiling)accepted=i+1;
    }
    return accepted;
}
}
