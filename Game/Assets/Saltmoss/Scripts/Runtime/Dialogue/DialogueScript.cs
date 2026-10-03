using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Dialogue scripts (Assets/Saltmoss/Resources/Dialogue/*.txt):
    /// <code>
    /// === node_id
    /// @walter happy: Ahoy there, {name}!{p} Welcome home.      speaker, expression, text (inline tags below)
    /// !gesture walter Wave                                       commands (see DialogueRunner)
    /// !if flag:met_walter -> walter_again                        conditional jump
    /// ? Ask about the boat -> walter_boat                       choices (shown together)
    /// ? Never mind -> end | if flag:x                            choice with a condition (if / unless)
    /// -> other_node                                              jump
    /// # comment
    /// </code>
    /// Inline: [expr] change expression mid-line · {p} short pause · {pp} long pause · {w}wavy{/w} · {s}shaky{/s}
    /// · {b}big{/b} · {c=#hex}colour{/c} · {spd=0.5} speed · {name} {money} {day} {item} variables.
    /// </summary>
    public static class DialogueScript
    {
        public enum StepKind { Line, Choice, Command, Goto }

        public class Choice { public string label, target, cond; }

        public class Step
        {
            public StepKind kind;
            public string speaker, expr, text;
            public List<Choice> choices;
            public string cmd;
            public string[] args;
            public string target;
            public int lineNo;
        }

        static Dictionary<string, List<Step>> nodes;

        public static void Load()
        {
            nodes = new Dictionary<string, List<Step>>();
            foreach (var ta in Resources.LoadAll<TextAsset>("Dialogue")) Parse(ta.text, ta.name);
        }

        public static List<Step> Node(string id)
        {
            if (nodes == null) Load();
            return id != null && nodes.TryGetValue(id, out var n) ? n : null;
        }

        public static bool Has(string id)
        {
            if (nodes == null) Load();
            return id != null && nodes.ContainsKey(id);
        }

        public static void Parse(string text, string file)
        {
            List<Step> cur = null;
            string[] lines = text.Replace("\r", "").Split('\n');
            for (int i = 0; i < lines.Length; i++)
            {
                string raw = lines[i];
                string l = raw.Trim();
                if (l.Length == 0 || l.StartsWith("#")) continue;
                if (l.StartsWith("==="))
                {
                    string id = l.Substring(3).Trim();
                    cur = new List<Step>();
                    nodes[id] = cur;
                    continue;
                }
                if (cur == null) { Debug.LogWarning($"[Dialogue] {file}:{i + 1} text outside a node"); continue; }
                if (l.StartsWith("@"))
                {
                    int colon = l.IndexOf(':');
                    if (colon < 0) { Debug.LogWarning($"[Dialogue] {file}:{i + 1} missing ':'"); continue; }
                    var head = l.Substring(1, colon - 1).Trim().Split(' ');
                    cur.Add(new Step { kind = StepKind.Line, speaker = head[0], expr = head.Length > 1 ? head[1] : "neutral", text = l.Substring(colon + 1).Trim(), lineNo = i + 1 });
                }
                else if (l.StartsWith("?"))
                {
                    var c = ParseChoice(l.Substring(1));
                    var last = cur.Count > 0 ? cur[cur.Count - 1] : null;
                    if (last == null || last.kind != StepKind.Choice) cur.Add(last = new Step { kind = StepKind.Choice, choices = new List<Choice>(), lineNo = i + 1 });
                    last.choices.Add(c);
                }
                else if (l.StartsWith("->"))
                    cur.Add(new Step { kind = StepKind.Goto, target = l.Substring(2).Trim(), lineNo = i + 1 });
                else if (l.StartsWith("!"))
                {
                    string body = l.Substring(1).Trim();
                    string target = null;
                    int arrow = body.IndexOf("->");
                    if (arrow >= 0) { target = body.Substring(arrow + 2).Trim(); body = body.Substring(0, arrow).Trim(); }
                    var parts = body.Split(new[] { ' ' }, System.StringSplitOptions.RemoveEmptyEntries);
                    var args = new string[parts.Length - 1];
                    System.Array.Copy(parts, 1, args, 0, args.Length);
                    cur.Add(new Step { kind = StepKind.Command, cmd = parts[0].ToLowerInvariant(), args = args, target = target, lineNo = i + 1 });
                }
                else
                {
                    // continuation of the previous line's text
                    var last = cur.Count > 0 ? cur[cur.Count - 1] : null;
                    if (last != null && last.kind == StepKind.Line) last.text += " " + l;
                }
            }
        }

        static Choice ParseChoice(string s)
        {
            string cond = null;
            int bar = s.IndexOf('|');
            if (bar >= 0) { cond = s.Substring(bar + 1).Trim(); s = s.Substring(0, bar); }
            string target = "end";
            int arrow = s.IndexOf("->");
            if (arrow >= 0) { target = s.Substring(arrow + 2).Trim(); s = s.Substring(0, arrow); }
            return new Choice { label = s.Trim(), target = target, cond = cond };
        }

        // ---------------------------------------------------------------- inline markup

        public enum MarkKind { Expr, Pause, Speed }

        public struct Mark
        {
            public int index;      // visible character index where it applies
            public MarkKind kind;
            public string value;
            public float f;
        }

        /// <summary>Converts script markup into TMP rich text plus timed marks (by visible character index).</summary>
        public static string Compile(string src, Dictionary<string, string> vars, List<Mark> marks)
        {
            marks.Clear();
            var sb = new StringBuilder();
            int visible = 0;
            int i = 0;
            while (i < src.Length)
            {
                char ch = src[i];
                if (ch == '[')
                {
                    int e = src.IndexOf(']', i);
                    if (e > i)
                    {
                        marks.Add(new Mark { index = visible, kind = MarkKind.Expr, value = src.Substring(i + 1, e - i - 1) });
                        i = e + 1;
                        continue;
                    }
                }
                if (ch == '{')
                {
                    int e = src.IndexOf('}', i);
                    if (e > i)
                    {
                        string tag = src.Substring(i + 1, e - i - 1);
                        i = e + 1;
                        switch (tag)
                        {
                            case "p": marks.Add(new Mark { index = visible, kind = MarkKind.Pause, f = 0.35f }); continue;
                            case "pp": marks.Add(new Mark { index = visible, kind = MarkKind.Pause, f = 0.9f }); continue;
                            case "w": sb.Append("<link=\"w\">"); continue;
                            case "s": sb.Append("<link=\"s\">"); continue;
                            case "/w":
                            case "/s": sb.Append("</link>"); continue;
                            case "b": sb.Append("<size=125%><b>"); continue;
                            case "/b": sb.Append("</b></size>"); continue;
                            case "/c": sb.Append("</color>"); continue;
                        }
                        if (tag.StartsWith("c=")) { sb.Append("<color=").Append(tag.Substring(2)).Append('>'); continue; }
                        if (tag.StartsWith("spd="))
                        {
                            float.TryParse(tag.Substring(4), System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var f);
                            marks.Add(new Mark { index = visible, kind = MarkKind.Speed, f = f <= 0 ? 1f : f });
                            continue;
                        }
                        if (vars != null && vars.TryGetValue(tag, out var v)) { sb.Append(v); visible += v.Length; continue; }
                        sb.Append('{').Append(tag).Append('}');
                        visible += tag.Length + 2;
                        continue;
                    }
                }
                sb.Append(ch);
                visible++;
                i++;
            }
            return sb.ToString();
        }
    }
}
