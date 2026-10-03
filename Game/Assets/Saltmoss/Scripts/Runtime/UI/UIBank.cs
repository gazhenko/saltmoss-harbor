using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Clay UI sprites and fonts (Resources/UIBank), built by the content pipeline.</summary>
    public class UIBank : ScriptableObject
    {
        public Sprite[] sprites = new Sprite[0];
        public TMP_FontAsset display, body;
        Dictionary<string, Sprite> map;
        static UIBank inst;

        public static UIBank I
        {
            get
            {
                if (inst == null) inst = Resources.Load<UIBank>("UIBank");
                if (inst == null) inst = CreateInstance<UIBank>();
                return inst;
            }
        }

        public Sprite Get(string name)
        {
            if (map == null)
            {
                map = new Dictionary<string, Sprite>();
                foreach (var s in sprites) if (s != null) map[s.name] = s;
            }
            return name != null && map.TryGetValue(name, out var sp) ? sp : null;
        }
    }
}
