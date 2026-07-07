# Build the 04-progressive-rollout console binary locally in this directory.
TARGET := 04-progressive-rollout
CXX ?= c++
CXXFLAGS := -std=c++20 -Wall -Wextra

REPO_ROOT := $(abspath $(CURDIR)/../../..)
VENV_PYTHON := $(REPO_ROOT)/.venv/bin/python3
CXXFLAGS += -DEVALUATE_HIGHLIGHT_SCRIPT=\"$(CURDIR)/evaluate_highlight.py\"
ifneq ($(wildcard $(VENV_PYTHON)),)
CXXFLAGS += -DDEFAULT_VENV_PYTHON=\"$(VENV_PYTHON)\"
endif

ifdef LDSDK_PREFIX
CXXFLAGS += -DHAS_LAUNCHDARKLY -I$(LDSDK_PREFIX)/include
LDFLAGS += -L$(LDSDK_PREFIX)/lib -llaunchdarkly-server-sdk -lcurl -lpthread
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): main.cpp flags.cpp flags.hpp
	$(CXX) $(CXXFLAGS) -o $(TARGET) main.cpp flags.cpp $(LDFLAGS)

clean:
	rm -f $(TARGET)
