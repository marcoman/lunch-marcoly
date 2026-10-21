using System.Text.Json.Nodes;
using LaunchDarkly.Sdk;

namespace AgentTools;

/// <summary>
/// Small, forgiving accessors over <see cref="JsonNode"/> — mirrors the defensive
/// <c>str(x.get(...) or "")</c> style used by the Python/Node ports so malformed
/// provider responses (Ollama/Anthropic/Yahoo) never crash the tool loop.
/// </summary>
internal static class JsonHelpers
{
    public static string GetStr(JsonObject? obj, string key, string fallback = "")
    {
        if (obj is null) return fallback;
        return NodeToStr(obj[key], fallback);
    }

    public static string NodeToStr(JsonNode? node, string fallback = "")
    {
        if (node is null) return fallback;
        try
        {
            if (node is JsonValue v)
            {
                if (v.TryGetValue<string>(out var s)) return s;
                return v.ToJsonString().Trim('"');
            }
        }
        catch
        {
            // fall through to fallback
        }
        return fallback;
    }

    public static int GetInt(JsonObject? obj, string key, int fallback = 0)
    {
        if (obj is null) return fallback;
        var node = obj[key];
        if (node is JsonValue v)
        {
            if (v.TryGetValue<int>(out var i)) return i;
            if (v.TryGetValue<long>(out var l)) return (int)l;
            if (v.TryGetValue<double>(out var d)) return (int)d;
        }
        return fallback;
    }

    public static bool GetBool(JsonObject? obj, string key, bool fallback = false)
    {
        if (obj is null) return fallback;
        var node = obj[key];
        if (node is JsonValue v && v.TryGetValue<bool>(out var b)) return b;
        return fallback;
    }

    public static JsonObject GetObj(JsonObject? obj, string key) =>
        obj?[key] as JsonObject ?? new JsonObject();

    public static JsonArray GetArr(JsonObject? obj, string key) =>
        obj?[key] as JsonArray ?? new JsonArray();

    /// <summary>Recursively converts an LdValue (LaunchDarkly SDK JSON type) into a JsonNode.</summary>
    public static JsonNode? LdValueToJsonNode(LdValue value)
    {
        switch (value.Type)
        {
            case LdValueType.Null:
                return null;
            case LdValueType.Bool:
                return JsonValue.Create(value.AsBool);
            case LdValueType.Number:
                return JsonValue.Create(value.AsDouble);
            case LdValueType.String:
                return JsonValue.Create(value.AsString);
            case LdValueType.Array:
                var arr = new JsonArray();
                foreach (var item in value.List)
                {
                    arr.Add(LdValueToJsonNode(item));
                }
                return arr;
            case LdValueType.Object:
                var obj = new JsonObject();
                foreach (var kv in value.Dictionary)
                {
                    obj[kv.Key] = LdValueToJsonNode(kv.Value);
                }
                return obj;
            default:
                return null;
        }
    }
}
