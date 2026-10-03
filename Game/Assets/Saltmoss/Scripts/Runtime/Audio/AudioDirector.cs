using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Music by context with crossfades, layered ambience, pooled 3D/2D effects and jingles that duck the music.
    /// </summary>
    public class AudioDirector : MonoBehaviour
    {
        public static AudioDirector I { get; private set; }
        public static AudioBank Bank { get; private set; }

        AudioSource[] music = new AudioSource[2];
        AudioSource[] amb = new AudioSource[3];
        AudioSource jingle;
        readonly List<AudioSource> pool = new List<AudioSource>();
        int musicIdx, poolIdx;
        string musicCue, ambCue, amb2Cue;
        float duck = 1f, duckUntil;
        float ambStorm;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (I != null) return;
            var go = new GameObject("AudioDirector");
            DontDestroyOnLoad(go);
            go.AddComponent<AudioDirector>();
            go.AddComponent<VoiceBlips>();
        }

        void Awake()
        {
            I = this;
            Bank = Resources.Load<AudioBank>("AudioBank");
            if (Bank == null) Bank = ScriptableObject.CreateInstance<AudioBank>();
            for (int i = 0; i < 2; i++) music[i] = Src(false, true);
            for (int i = 0; i < 3; i++) amb[i] = Src(false, true);
            jingle = Src(false, false);
            for (int i = 0; i < 20; i++) pool.Add(Src(true, false));
        }

        AudioSource Src(bool spatial, bool loop)
        {
            var a = gameObject.AddComponent<AudioSource>();
            a.playOnAwake = false;
            a.loop = loop;
            a.spatialBlend = spatial ? 1f : 0f;
            a.rolloffMode = AudioRolloffMode.Linear;
            a.minDistance = 3f;
            a.maxDistance = 45f;
            a.dopplerLevel = 0f;
            return a;
        }

        public void Music(string cue)
        {
            if (cue == musicCue) return;
            musicCue = cue;
            var clip = Bank.Get(cue);
            musicIdx = 1 - musicIdx;
            var a = music[musicIdx];
            a.clip = clip;
            a.volume = 0f;
            if (clip != null) a.Play();
        }

        public void Ambience(string main, string layer2 = null)
        {
            if (main != ambCue)
            {
                ambCue = main;
                var a = amb[0].isPlaying && amb[0].clip != null && amb[0].clip.name == main ? amb[0] : null;
                if (a == null)
                {
                    // swap: the current main fades out on slot 2
                    (amb[0], amb[2]) = (amb[2], amb[0]);
                    amb[0].clip = Bank.Get(main);
                    amb[0].volume = 0f;
                    if (amb[0].clip != null) amb[0].Play();
                }
            }
            if (layer2 != amb2Cue)
            {
                amb2Cue = layer2;
                amb[1].clip = Bank.Get(layer2);
                if (amb[1].clip != null) amb[1].Play(); else amb[1].Stop();
            }
        }

        public void StormAmount(float s) => ambStorm = s;

        public void Jingle(string name, float duckFor = -1f)
        {
            var c = Bank.Get(name);
            if (c == null) return;
            jingle.clip = c;
            jingle.volume = Settings.Music * 1.1f;
            jingle.Play();
            duckUntil = Time.unscaledTime + (duckFor > 0 ? duckFor : c.length);
        }

        public static void Play(string name, Vector3 pos, float vol = 1f, float pitchVar = 0.06f, float pitch = 1f)
        {
            if (I == null) return;
            var c = Bank.Variant(name);
            if (c == null) return;
            var a = I.pool[I.poolIdx];
            I.poolIdx = (I.poolIdx + 1) % I.pool.Count;
            a.transform.position = pos;
            a.spatialBlend = 1f;
            a.clip = c;
            a.pitch = pitch * (1f + (Random.value - 0.5f) * 2f * pitchVar);
            a.volume = vol * Settings.Sfx;
            a.Play();
        }

        public static void UI(string name, float vol = 0.8f, float pitchVar = 0.04f)
        {
            if (I == null) return;
            var c = Bank.Variant(name);
            if (c == null) return;
            var a = I.pool[I.poolIdx];
            I.poolIdx = (I.poolIdx + 1) % I.pool.Count;
            a.spatialBlend = 0f;
            a.clip = c;
            a.pitch = 1f + (Random.value - 0.5f) * 2f * pitchVar;
            a.volume = vol * Settings.Sfx;
            a.Play();
        }

        public static void Footstep(string surface, Vector3 pos) => Play("step_" + surface, pos, 0.45f, 0.1f);

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            float target = Time.unscaledTime < duckUntil ? 0.25f : 1f;
            duck = Mathf.MoveTowards(duck, target, dt * (target < duck ? 4f : 0.8f));
            for (int i = 0; i < 2; i++)
            {
                float want = i == musicIdx ? Settings.Music * 0.8f * duck : 0f;
                music[i].volume = Mathf.MoveTowards(music[i].volume, want, dt * 0.35f);
                if (i != musicIdx && music[i].volume <= 0.001f && music[i].isPlaying) music[i].Stop();
            }
            amb[0].volume = Mathf.MoveTowards(amb[0].volume, Settings.Ambience * 0.9f, dt * 0.3f);
            amb[2].volume = Mathf.MoveTowards(amb[2].volume, 0f, dt * 0.3f);
            if (amb[2].volume <= 0.001f && amb[2].isPlaying) amb[2].Stop();
            amb[1].volume = Mathf.MoveTowards(amb[1].volume, Settings.Ambience * 0.8f * Mathf.Clamp01(ambStorm + 0.3f), dt * 0.3f);
        }
    }
}
