#pragma once
#include <array>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <unordered_map>
#include <vector>

namespace er {
inline constexpr size_t PayloadSize=0x200;
struct Message {
    uint64_t id{};
    uint32_t map{},area{},secondaryArea{};
    std::array<float,3> position{};
    float yaw{};
    uint16_t template1{},word1{},conjunction{},template2{},word2{},good{},poor{};
    void WriteFields(std::span<uint8_t,PayloadSize>) const noexcept;
};
struct MessagePack {
    std::string source;
    std::vector<Message> messages;
    std::unordered_map<uint32_t,std::vector<size_t>> byMap;
    static MessagePack Parse(const std::string&);
    static MessagePack Load(const std::filesystem::path&);
};
}
