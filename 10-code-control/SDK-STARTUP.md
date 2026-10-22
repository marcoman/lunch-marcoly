# Server SDK startup by language

These are the common LaunchDarkly **server SDK** startup steps used throughout
the 10-code-control examples. Each application creates one client for the
process, reuses it for flag evaluations, and closes it during shutdown.

Set the environment's server-side SDK key first:

```bash
export LD_SDK_KEY="sdk-..."
```

Treat this key as a secret. Do not put it in browser code or commit it.

## Python

Install the [Python server SDK](https://launchdarkly.com/docs/sdk/server-side/python):

```bash
pip install launchdarkly-server-sdk
```

```python
import os
import ldclient
from ldclient.config import Config

ldclient.set_config(Config(os.environ["LD_SDK_KEY"]))
ld_client = ldclient.get()

# Reuse ld_client for every evaluation.
# On shutdown:
ld_client.close()
```

## Node.js

Install the [Node.js server SDK](https://launchdarkly.com/docs/sdk/server-side/node-js):

```bash
npm install @launchdarkly/node-server-sdk
```

```javascript
const LaunchDarkly = require("@launchdarkly/node-server-sdk");

const ldClient = LaunchDarkly.init(process.env.LD_SDK_KEY);
await ldClient.waitForInitialization({ timeout: 5 });

// Reuse ldClient for every evaluation.
// On shutdown:
ldClient.close();
```

## Java

Add the [Java server SDK](https://launchdarkly.com/docs/sdk/server-side/java) to
`pom.xml`:

```xml
<dependency>
  <groupId>com.launchdarkly</groupId>
  <artifactId>launchdarkly-java-server-sdk</artifactId>
  <version>7.6.0</version>
</dependency>
```

```java
import com.launchdarkly.sdk.server.LDClient;

LDClient ldClient = new LDClient(System.getenv("LD_SDK_KEY"));

// Reuse ldClient for every evaluation.
// On shutdown:
ldClient.close();
```

## .NET

Install the [.NET server SDK](https://launchdarkly.com/docs/sdk/server-side/dotnet):

```bash
dotnet add package LaunchDarkly.ServerSdk --version 8.16.0
```

```csharp
using LaunchDarkly.Sdk.Server;

using var ldClient = new LdClient(
    Configuration.Builder(
        Environment.GetEnvironmentVariable("LD_SDK_KEY")
    ).StartWaitTime(TimeSpan.FromSeconds(5)).Build()
);

// Reuse ldClient for every evaluation.
```

## Go

Install the [Go server SDK](https://launchdarkly.com/docs/sdk/server-side/go):

```bash
go get github.com/launchdarkly/go-server-sdk/v7
```

```go
import (
	"os"
	"time"

	ld "github.com/launchdarkly/go-server-sdk/v7"
)

ldClient, err := ld.MakeClient(os.Getenv("LD_SDK_KEY"), 5*time.Second)
if err != nil {
	panic(err)
}
defer ldClient.Close()

// Reuse ldClient for every evaluation.
```

## Rust

Install the [Rust server SDK](https://launchdarkly.com/docs/sdk/server-side/rust):

```bash
cargo add launchdarkly-server-sdk@2.6
```

```rust
use launchdarkly_server_sdk::{Client, ConfigBuilder};

let config = ConfigBuilder::new(&std::env::var("LD_SDK_KEY")?).build()?;
let ld_client = Client::build(config)?;
ld_client.start_with_runtime()?;

// Reuse ld_client for every evaluation.
// On shutdown:
ld_client.close();
```

## C++

The C++ examples can link the
[LaunchDarkly C server SDK](https://launchdarkly.com/docs/sdk/server-side/c).
Build that SDK, then point this repository's Makefile at its install prefix:

```bash
LDSDK_PREFIX=/path/to/ld-sdk make all
```

```cpp
extern "C" {
#include <launchdarkly/client.h>
}

LDClient* ld_client =
    LDClientInitFromSDKKey(std::getenv("LD_SDK_KEY"), 5000, nullptr);

// Reuse ld_client for every evaluation.
// On shutdown:
LDClientClose(ld_client);
```

The application-specific examples add the evaluation
[context](https://launchdarkly.com/docs/home/flags/contexts), call a typed
flag variation, and use the returned value in application behavior.
