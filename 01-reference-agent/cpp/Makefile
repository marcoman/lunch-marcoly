# Build the 01-reference-agent console binary locally in this directory.
TARGET := 01-reference-agent
CXX ?= c++
CXXFLAGS := -std=c++20 -Wall -Wextra -Ithird_party -I.
LDFLAGS := -lcurl

SRCS := main.cpp yahoo.cpp agent.cpp
JSON_HPP := third_party/nlohmann/json.hpp

.PHONY: all clean

all: $(TARGET)

$(JSON_HPP):
	mkdir -p $(dir $@)
	curl -fsSL -o $@ https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp

$(TARGET): $(SRCS) yahoo.hpp agent.hpp $(JSON_HPP)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRCS) $(LDFLAGS)

clean:
	rm -f $(TARGET)
