# Build the 10-flag-enablement console binary locally in this directory.
TARGET := 10-flag-enablement
CXX ?= c++
CXXFLAGS := -std=c++20 -Wall -Wextra

# Optional: link the LaunchDarkly C server SDK when LDSDK_PREFIX is set.
# See: https://launchdarkly.com/docs/sdk/server-side/c
REPO_ROOT := $(abspath $(CURDIR)/../..)
VENV_PYTHON := $(REPO_ROOT)/.venv/bin/python3
CXXFLAGS += -DEVALUATE_FLAGS_SCRIPT=\"$(CURDIR)/evaluate_flags.py\"
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
