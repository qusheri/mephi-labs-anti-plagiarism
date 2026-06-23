CXX ?= c++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Wpedantic -O2

BUILD_DIR := build
INCLUDES := -Iinclude
SOURCES := src/tokenizer.cpp src/detectors.cpp
TEST_SOURCES := tests/algos_test.cpp
TEST_BINARY := $(BUILD_DIR)/antiplag_algos_tests

.PHONY: all test clean

all: test

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(TEST_BINARY): $(SOURCES) $(TEST_SOURCES) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SOURCES) $(TEST_SOURCES) -o $(TEST_BINARY)

test: $(TEST_BINARY)
	./$(TEST_BINARY)

clean:
	rm -rf $(BUILD_DIR)
