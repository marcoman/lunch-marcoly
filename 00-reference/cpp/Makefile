# Build the 00-reference console binary locally in this directory.
TARGET := 00-reference
CXX ?= c++
CXXFLAGS := -std=c++20 -Wall -Wextra

.PHONY: all clean

all: $(TARGET)

$(TARGET): main.cpp
	$(CXX) $(CXXFLAGS) -o $(TARGET) main.cpp

clean:
	rm -f $(TARGET)
