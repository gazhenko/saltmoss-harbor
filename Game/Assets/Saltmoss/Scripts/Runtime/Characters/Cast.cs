using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Who's who: display names, name-tag colours, voices, models and portrait framing.</summary>
    public class CastMember
    {
        public string id, name, model, voice;
        public Color tag;
        public Color backdrop;
        public float personality = 1f;
        public float portraitDistance = 1.0f;   // multiplier on the bust framing distance
    }

    public static class Cast
    {
        static Color C(string hex) { ColorUtility.TryParseHtmlString(hex, out var c); return c; }

        public static readonly Dictionary<string, CastMember> All = new Dictionary<string, CastMember>
        {
            ["pip"] = new CastMember { id = "pip", name = "Pip", model = "chars/pip", voice = "pip", tag = C("#e0a52a"), backdrop = C("#f3d98a"), personality = 1.1f },
            ["walter"] = new CastMember { id = "walter", name = "Walter", model = "chars/walter", voice = "walter", tag = C("#2f3d5c"), backdrop = C("#9db3c9"), personality = 0.8f, portraitDistance = 1.15f },
            ["nell"] = new CastMember { id = "nell", name = "Nell", model = "chars/nell", voice = "nell", tag = C("#3f7f7c"), backdrop = C("#a9d1c6"), personality = 1.2f },
            ["marge"] = new CastMember { id = "marge", name = "Marge", model = "chars/marge", voice = "marge", tag = C("#7a4f8f"), backdrop = C("#d3bfe0"), personality = 1f, portraitDistance = 1.1f },
            ["inkwell"] = new CastMember { id = "inkwell", name = "Professor Inkwell", model = "chars/inkwell", voice = "inkwell", tag = C("#8a3b5c"), backdrop = C("#e3b9c6"), personality = 1f, portraitDistance = 1.1f },
            ["shelby"] = new CastMember { id = "shelby", name = "Shelby", model = "chars/shelby", voice = "shelby", tag = C("#d0612f"), backdrop = C("#f6c9a6"), personality = 1.4f },
            ["gull"] = new CastMember { id = "gull", name = "Customer", model = "chars/cust_gull", voice = "gull", tag = C("#7d8c99"), backdrop = C("#dfe6ec") },
            ["crab"] = new CastMember { id = "crab", name = "Customer", model = "chars/cust_crab", voice = "crab", tag = C("#b8432f"), backdrop = C("#f2c5b8") },
            ["seal"] = new CastMember { id = "seal", name = "Customer", model = "chars/cust_seal", voice = "seal", tag = C("#5d6670"), backdrop = C("#cfd6dc") },
        };

        public static CastMember Get(string id) => id != null && All.TryGetValue(id, out var c) ? c : All["pip"];
    }
}
