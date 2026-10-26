#include "CacheBudget.h"
#include <vector>
#include <stdexcept>
#include <iostream>
void Require(bool ok){if(!ok)throw std::runtime_error("Cache budget invariant");}
int main(){
    try{
        std::vector<size_t> candidates;for(size_t i=0;i<96;++i)candidates.push_back(i);
        std::vector<er::CacheResident> residents(56); // Original client objects.
        Require(er::CachePrefix(candidates,residents,128)==64);
        // Adjacent-map bindings also reserve capacity, even after a scene change.
        for(size_t i=100;i<140;++i)residents.push_back({i,true});
        Require(er::CachePrefix(candidates,residents,128)==24);
        // Current protected own nodes already in the prefix must not be double counted.
        for(size_t i=0;i<12;++i)residents.push_back({i,true});
        Require(er::CachePrefix(candidates,residents,128)==24);
        // Unbound own nodes outside selection can be retired by the native lifecycle.
        for(size_t i=200;i<240;++i)residents.push_back({i,false});
        Require(er::CachePrefix(candidates,residents,128)==24);
        // Foreign saturation never authorizes new records or native-object deletion.
        residents.assign(128,{});Require(er::CachePrefix(candidates,residents,128)==0);
        residents.clear();Require(er::CachePrefix(candidates,residents,128)==96);
        // A protected far candidate must not justify admitting nearer records beyond headroom.
        residents.assign(119,{});residents.push_back({95,true});
        Require(er::CachePrefix(candidates,residents,128)==0);
        std::cout<<"Resident cache budget tests passed; no gameplay implied\n";return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
