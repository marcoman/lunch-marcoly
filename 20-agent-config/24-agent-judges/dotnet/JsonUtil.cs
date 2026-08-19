using System.Collections;
using System.Text.Json.Nodes;

namespace AgentJudges;

/// <summary>
/// Small helpers for converting between <see cref="JsonNode"/> trees and the loosely typed
/// <c>Dictionary&lt;string, object?&gt;</c> shape used throughout this example (mirrors the
/// plain-object/Map style used by the Node and Java ports of 24-agent-judges).
/// </summary>
internal static class JsonUtil
{
    public static string? AsString(JsonNode? node)
        => node is JsonValue v && v.TryGetValue<string>(out var s) ? s : null;

    public static long? AsLong(JsonNode? node)
    {
        if (node is not JsonValue v) return null;
        if (v.TryGetValue<long>(out var l)) return l;
        if (v.TryGetValue<double>(out var d)) return (long)d;
        if (v.TryGetValue<string>(out var s) && long.TryParse(s, out var parsed)) return parsed;
        return null;
    }

    public static object? ToObject(JsonNode? node)
    {
        switch (node)
        {
            case null:
                return null;
            case JsonObject o:
                return ToMap(o);
            case JsonArray a:
                return a.Select(ToObject).ToList();
            case JsonValue v:
                if (v.TryGetValue<string>(out var s)) return s;
                if (v.TryGetValue<bool>(out var b)) return b;
                if (v.TryGetValue<long>(out var l)) return l;
                if (v.TryGetValue<double>(out var d)) return d;
                return node.ToString();
            default:
                return node.ToString();
        }
    }

    public static Dictionary<string, object?> ToMap(JsonObject obj)
    {
        var map = new Dictionary<string, object?>();
        foreach (var kv in obj)
        {
            map[kv.Key] = ToObject(kv.Value);
        }
        return map;
    }

    public static JsonNode? FromObject(object? value)
    {
        switch (value)
        {
            case null:
                return null;
            case string s:
                return JsonValue.Create(s);
            case bool b:
                return JsonValue.Create(b);
            case int i:
                return JsonValue.Create(i);
            case long l:
                return JsonValue.Create(l);
            case double d:
                return JsonValue.Create(d);
            case Dictionary<string, object?> map:
                return FromMap(map);
            case IEnumerable list:
                return FromList(list);
            default:
                return JsonValue.Create(value.ToString());
        }
    }

    public static JsonObject FromMap(Dictionary<string, object?> map)
    {
        var obj = new JsonObject();
        foreach (var kv in map)
        {
            obj[kv.Key] = FromObject(kv.Value);
        }
        return obj;
    }

    private static JsonArray FromList(IEnumerable list)
    {
        var arr = new JsonArray();
        foreach (var item in list)
        {
            arr.Add(FromObject(item));
        }
        return arr;
    }
}
