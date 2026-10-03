using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace Saltmoss
{
    /// <summary>
    /// Scripted keyboard input for automated play-throughs of a build:
    ///   -keys "2:e:tap,3.5:w:down,6:w:up,8:space:down,12:space:up"   (seconds since start : key : tap|down|up)
    /// Key names are UnityEngine.InputSystem.Key names (e, w, space, leftShift, tab, escape, enter…).
    /// </summary>
    public class AutoKeys : MonoBehaviour
    {
        struct Ev { public float t; public Key key; public int action; }   // 0 tap, 1 down, 2 up
        readonly List<Ev> events = new List<Ev>();
        readonly HashSet<Key> held = new HashSet<Key>();
        readonly List<Key> releaseNext = new List<Key>();
        int next;
        float start;
        Keyboard kb;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            var spec = CommandLine.Get("-keys");
            if (spec == null) return;
            var go = new GameObject("AutoKeys");
            DontDestroyOnLoad(go);
            var a = go.AddComponent<AutoKeys>();
            foreach (var item in spec.Split(','))
            {
                var p = item.Split(':');
                if (p.Length < 2) continue;
                if (!System.Enum.TryParse<Key>(p[1], true, out var k)) { Debug.LogWarning("[AutoKeys] unknown key " + p[1]); continue; }
                int act = p.Length > 2 ? (p[2] == "down" ? 1 : p[2] == "up" ? 2 : 0) : 0;
                a.events.Add(new Ev { t = float.Parse(p[0], CultureInfo.InvariantCulture), key = k, action = act });
            }
            a.events.Sort((x, y) => x.t.CompareTo(y.t));
        }

        void Start()
        {
            start = Time.unscaledTime;
            kb = Keyboard.current ?? InputSystem.AddDevice<Keyboard>("AutoKeyboard");
        }

        void Update()
        {
            bool changed = releaseNext.Count > 0;
            foreach (var k in releaseNext) held.Remove(k);
            releaseNext.Clear();
            float t = Time.unscaledTime - start;
            while (next < events.Count && events[next].t <= t)
            {
                var e = events[next++];
                if (e.action == 2) held.Remove(e.key);
                else held.Add(e.key);
                if (e.action == 0) releaseNext.Add(e.key);
                changed = true;
                Debug.Log($"[AutoKeys] {t:0.0}s {e.key} {(e.action == 0 ? "tap" : e.action == 1 ? "down" : "up")}");
            }
            if (!changed || kb == null) return;
            var state = new KeyboardState();
            foreach (var k in held) state.Set(k, true);
            InputSystem.QueueStateEvent(kb, state);
        }
    }
}
