import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Minimal JSON codec used by the dependency-free lab REST endpoints. */
final class Json {
    private Json() {
    }

    static Object parse(String text) {
        Parser parser = new Parser(text == null ? "" : text);
        Object value = parser.value();
        parser.whitespace();
        if (!parser.atEnd()) {
            throw new IllegalArgumentException("Unexpected JSON after position " + parser.position);
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> parseObject(String text) {
        Object value = parse(text);
        if (!(value instanceof Map<?, ?>)) {
            throw new IllegalArgumentException("Request body must be a JSON object");
        }
        return (Map<String, Object>) value;
    }

    static String stringify(Object value) {
        if (value == null) {
            return "null";
        }
        if (value instanceof String string) {
            return "\"" + escape(string) + "\"";
        }
        if (value instanceof Boolean || value instanceof Number) {
            return value.toString();
        }
        if (value instanceof Map<?, ?> map) {
            StringBuilder out = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!first) out.append(',');
                first = false;
                out.append(stringify(String.valueOf(entry.getKey())))
                        .append(':')
                        .append(stringify(entry.getValue()));
            }
            return out.append('}').toString();
        }
        if (value instanceof Iterable<?> iterable) {
            StringBuilder out = new StringBuilder("[");
            boolean first = true;
            for (Object item : iterable) {
                if (!first) out.append(',');
                first = false;
                out.append(stringify(item));
            }
            return out.append(']').toString();
        }
        return stringify(value.toString());
    }

    static String escape(String value) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        return out.toString();
    }

    private static final class Parser {
        private final String text;
        private int position;

        private Parser(String text) {
            this.text = text;
        }

        private boolean atEnd() {
            return position >= text.length();
        }

        private void whitespace() {
            while (!atEnd() && Character.isWhitespace(text.charAt(position))) position++;
        }

        private Object value() {
            whitespace();
            if (atEnd()) throw error("Expected JSON value");
            return switch (text.charAt(position)) {
                case '{' -> object();
                case '[' -> array();
                case '"' -> string();
                case 't' -> literal("true", true);
                case 'f' -> literal("false", false);
                case 'n' -> literal("null", null);
                default -> number();
            };
        }

        private Map<String, Object> object() {
            position++;
            Map<String, Object> result = new LinkedHashMap<>();
            whitespace();
            if (consume('}')) return result;
            while (true) {
                whitespace();
                if (atEnd() || text.charAt(position) != '"') throw error("Expected object key");
                String key = string();
                whitespace();
                require(':');
                result.put(key, value());
                whitespace();
                if (consume('}')) return result;
                require(',');
            }
        }

        private List<Object> array() {
            position++;
            List<Object> result = new ArrayList<>();
            whitespace();
            if (consume(']')) return result;
            while (true) {
                result.add(value());
                whitespace();
                if (consume(']')) return result;
                require(',');
            }
        }

        private String string() {
            require('"');
            StringBuilder out = new StringBuilder();
            while (!atEnd()) {
                char c = text.charAt(position++);
                if (c == '"') return out.toString();
                if (c != '\\') {
                    out.append(c);
                    continue;
                }
                if (atEnd()) throw error("Unterminated escape");
                char escaped = text.charAt(position++);
                switch (escaped) {
                    case '"', '\\', '/' -> out.append(escaped);
                    case 'b' -> out.append('\b');
                    case 'f' -> out.append('\f');
                    case 'n' -> out.append('\n');
                    case 'r' -> out.append('\r');
                    case 't' -> out.append('\t');
                    case 'u' -> {
                        if (position + 4 > text.length()) throw error("Invalid unicode escape");
                        out.append((char) Integer.parseInt(text.substring(position, position + 4), 16));
                        position += 4;
                    }
                    default -> throw error("Invalid escape");
                }
            }
            throw error("Unterminated string");
        }

        private Object number() {
            int start = position;
            if (consume('-')) {
                // sign consumed
            }
            while (!atEnd() && Character.isDigit(text.charAt(position))) position++;
            boolean decimal = false;
            if (consume('.')) {
                decimal = true;
                while (!atEnd() && Character.isDigit(text.charAt(position))) position++;
            }
            if (!atEnd() && (text.charAt(position) == 'e' || text.charAt(position) == 'E')) {
                decimal = true;
                position++;
                if (!atEnd() && (text.charAt(position) == '+' || text.charAt(position) == '-')) position++;
                while (!atEnd() && Character.isDigit(text.charAt(position))) position++;
            }
            if (start == position) throw error("Expected JSON value");
            String token = text.substring(start, position);
            try {
                return decimal ? Double.parseDouble(token) : Long.parseLong(token);
            } catch (NumberFormatException exception) {
                throw error("Invalid number");
            }
        }

        private Object literal(String token, Object value) {
            if (!text.startsWith(token, position)) throw error("Invalid JSON value");
            position += token.length();
            return value;
        }

        private boolean consume(char expected) {
            if (!atEnd() && text.charAt(position) == expected) {
                position++;
                return true;
            }
            return false;
        }

        private void require(char expected) {
            if (!consume(expected)) throw error("Expected '" + expected + "'");
        }

        private IllegalArgumentException error(String message) {
            return new IllegalArgumentException(message + " at position " + position);
        }
    }
}
