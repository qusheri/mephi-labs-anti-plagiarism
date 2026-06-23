cmake_minimum_required(VERSION 3.16)

project(antiplag_algos LANGUAGES CXX)

add_library(antiplag_algos
    src/detectors.cpp
    src/tokenizer.cpp
)

target_include_directories(antiplag_algos
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(antiplag_algos PUBLIC cxx_std_17)

option(ANTIPLAG_ALGOS_BUILD_TESTS "Build antiplag algorithm tests" ON)

if(ANTIPLAG_ALGOS_BUILD_TESTS)
    add_executable(antiplag_algos_tests
        tests/algos_test.cpp
    )
    target_link_libraries(antiplag_algos_tests PRIVATE antiplag_algos)
endif()
