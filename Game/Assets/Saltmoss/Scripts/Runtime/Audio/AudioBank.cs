using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Clip lookup by file name, built by the content pipeline (Resources/AudioBank).</summary>
    public class AudioBank : ScriptableObject
    {
        public AudioClip[] clips = new AudioClip[0];
        Dictionary<string, AudioClip> map;

        public AudioClip Get(string name)
        {
            if (map == null)
            {
                map = new Dictionary<string, AudioClip>();
                foreach (var c in clips) if (c != null) map[c.name] = c;
            }
            return name != null && map.TryGetValue(name, out var a) ? a : null;
        }

        /// <summary>Random variant: name_1..name_n, or the bare name.</summary>
        public AudioClip Variant(string name)
        {
            Get(name);
            int n = 0;
            while (map.ContainsKey($"{name}_{n + 1}")) n++;
            return n > 0 ? map[$"{name}_{Random.Range(1, n + 1)}"] : Get(name);
        }
    }
}
