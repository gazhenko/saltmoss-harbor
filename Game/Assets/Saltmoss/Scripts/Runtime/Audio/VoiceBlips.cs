using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>One character's voice: pitch, vocal-tract size and the little quirks that make them sound like them.</summary>
    public class VoiceProfile
    {
        public string id;
        public float pitch = 220f;        // glottal pitch (Hz)
        public float formant = 1f;        // vocal-tract scale: >1 = smaller creature, brighter vowels
        public float speed = 22f;         // syllables per second when babbling
        public float breath = 0.08f;      // aspiration noise
        public float growl;               // subharmonic rasp (walrus)
        public float nasal;               // honk resonance (pelican, gull)
        public float bubble;              // bubbly pops and wobble (octopus)
        public float vibrato;             // pitch wobble depth (fraction)
        public float pitchVar = 0.06f;    // random pitch per syllable
        public float squeak;              // high squeaky overtone (hermit crab)
        public float volume = 0.7f;
        public string[] mumbles = { "hm hm", "oh", "ah-ha" };
    }

    /// <summary>
    /// Animalese-style voice blips: each letter is a short synthesized syllable (formant synthesis over a glottal pulse)
    /// at the character's pitch, built once per character at startup. Letters map to their letter-name vowel with a
    /// consonant onset (plosive burst, fricative hiss, nasal hum, liquid glide). Speaking pitch-shifts each blip along
    /// an intonation contour; mumbles string syllables together for greetings and reactions.
    /// </summary>
    public class VoiceBlips : MonoBehaviour
    {
        public static VoiceBlips I { get; private set; }
        const int Rate = 44100;

        static readonly Dictionary<string, VoiceProfile> profiles = new Dictionary<string, VoiceProfile>
        {
            ["pip"] = new VoiceProfile { id = "pip", pitch = 330f, formant = 1.22f, speed = 24f, breath = 0.06f, pitchVar = 0.07f, volume = 0.6f, mumbles = new[] { "oh!", "hm?", "yay", "ooh" } },
            ["walter"] = new VoiceProfile { id = "walter", pitch = 98f, formant = 0.8f, speed = 15f, breath = 0.12f, growl = 0.65f, pitchVar = 0.04f, volume = 0.85f, mumbles = new[] { "hrrm", "harumph", "ahoy", "hm-hm" } },
            ["nell"] = new VoiceProfile { id = "nell", pitch = 245f, formant = 1.08f, speed = 21f, breath = 0.18f, pitchVar = 0.06f, volume = 0.65f, mumbles = new[] { "oh hey", "mm-hm", "ha!", "ooh" } },
            ["marge"] = new VoiceProfile { id = "marge", pitch = 285f, formant = 1.0f, speed = 20f, breath = 0.05f, nasal = 0.85f, pitchVar = 0.08f, volume = 0.62f, mumbles = new[] { "well!", "ahem", "oh my", "hmph" } },
            ["inkwell"] = new VoiceProfile { id = "inkwell", pitch = 160f, formant = 0.95f, speed = 17f, breath = 0.1f, bubble = 0.75f, vibrato = 0.035f, pitchVar = 0.05f, volume = 0.75f, mumbles = new[] { "ah-ha", "hmm", "splendid", "oho" } },
            ["shelby"] = new VoiceProfile { id = "shelby", pitch = 470f, formant = 1.38f, speed = 28f, breath = 0.04f, squeak = 0.6f, pitchVar = 0.1f, volume = 0.55f, mumbles = new[] { "wow!", "hee", "ooh!", "mine!" } },
            ["gull"] = new VoiceProfile { id = "gull", pitch = 400f, formant = 1.2f, speed = 25f, breath = 0.1f, nasal = 0.6f, pitchVar = 0.12f, volume = 0.55f, mumbles = new[] { "kyah", "hm", "ooh" } },
            ["crab"] = new VoiceProfile { id = "crab", pitch = 380f, formant = 1.3f, speed = 30f, breath = 0.03f, squeak = 0.3f, pitchVar = 0.1f, volume = 0.5f, mumbles = new[] { "tik tik", "hm", "oh" } },
            ["seal"] = new VoiceProfile { id = "seal", pitch = 190f, formant = 0.95f, speed = 19f, breath = 0.2f, growl = 0.15f, pitchVar = 0.07f, volume = 0.6f, mumbles = new[] { "arf", "hm-hm", "ooh" } },
        };

        public static VoiceProfile Profile(string id) => id != null && profiles.TryGetValue(id, out var p) ? p : profiles["pip"];

        readonly Dictionary<string, AudioClip[]> clips = new Dictionary<string, AudioClip[]>();
        readonly List<AudioSource> pool = new List<AudioSource>();
        int next;
        float lastBlip;

        // letter -> (onset kind, vowel). Onsets: 0 none, 1 voiced plosive, 2 unvoiced plosive, 3 hiss, 4 soft fricative, 5 nasal, 6 liquid, 7 breathy h
        static readonly int[] Onset = { 0, 1, 2, 1, 0, 4, 1, 7, 0, 1, 2, 6, 5, 5, 0, 2, 2, 6, 3, 2, 0, 4, 6, 3, 0, 3 };
        static readonly int[] Vowel = { 0, 2, 2, 2, 2, 1, 2, 0, 3, 1, 1, 1, 1, 1, 3, 2, 4, 0, 1, 2, 4, 2, 4, 1, 3, 2 };   // 0 A, 1 E, 2 I, 3 O, 4 U
        static readonly float[,] F = { { 750, 1150, 2500 }, { 540, 1820, 2520 }, { 300, 2250, 3000 }, { 560, 860, 2450 }, { 330, 900, 2300 } };

        void Awake()
        {
            I = this;
            for (int i = 0; i < 6; i++)
            {
                var a = gameObject.AddComponent<AudioSource>();
                a.playOnAwake = false;
                a.spatialBlend = 0f;
                a.priority = 40;
                pool.Add(a);
            }
        }

        AudioClip[] Clips(VoiceProfile p)
        {
            if (clips.TryGetValue(p.id, out var c)) return c;
            var rng = new System.Random(p.id.GetHashCode());
            c = new AudioClip[26];
            for (int i = 0; i < 26; i++) c[i] = Build(p, i, rng);
            clips[p.id] = c;
            return c;
        }

        /// <summary>Make sure a voice is synthesized before it is needed (avoid a hitch at the first line).</summary>
        public void Warm(string id) => Clips(Profile(id));

        static AudioClip Build(VoiceProfile p, int letter, System.Random rng)
        {
            float dur = Mathf.Clamp(1.35f / p.speed, 0.045f, 0.11f);
            int n = (int)(dur * Rate);
            int onset = Onset[letter];
            int v = Vowel[letter];
            var buf = new float[n];
            // formant resonators (2-pole) for the vowel; liquids glide in from a dark /l/-ish shape
            float fs = p.formant;
            double phase = 0, sub = 0;
            var res = new Reson[3];
            var aspRes = new Reson[3];
            float onsetLen = onset == 0 ? 0f : onset == 1 || onset == 2 ? 0.012f : onset == 5 || onset == 6 ? 0.022f : 0.026f;
            int onN = (int)(onsetLen * Rate);
            float jitter = 0f;
            float bubbleAt = (float)rng.NextDouble() * 0.6f + 0.2f;
            for (int i = 0; i < n; i++)
            {
                float t = i / (float)Rate;
                float k = i / (float)n;
                // formant targets (glide from the onset shape into the vowel)
                float g = onset == 6 || onset == 5 ? Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((i - onN * 0.3f) / (onN * 1.2f + 1))) : 1f;
                float f1 = Mathf.Lerp(onset == 5 ? 260f : 320f, F[v, 0], g) * fs;
                float f2 = Mathf.Lerp(onset == 5 ? 1100f : 950f, F[v, 1], g) * fs;
                float f3 = F[v, 2] * fs;
                if (p.nasal > 0f) f1 *= 1f - p.nasal * 0.25f;
                if (i % 32 == 0)
                {
                    res[0].Set(f1, 80f * fs);
                    res[1].Set(f2, 110f * fs);
                    res[2].Set(f3, 160f * fs);
                    aspRes[0].Set(f1, 200f); aspRes[1].Set(f2, 260f); aspRes[2].Set(f3, 320f);
                }
                // glottal source: band-limited-ish pulse (sum of a few harmonics shaped like a glottal spectrum)
                float f0 = p.pitch * (1f + p.vibrato * Mathf.Sin(t * 2f * Mathf.PI * 7.5f)) * (1f + 0.04f * (1f - k));   // slight fall
                if (p.growl > 0f && i % 220 == 0) jitter = ((float)rng.NextDouble() - 0.5f) * 0.06f * p.growl;
                f0 *= 1f + jitter;
                phase += f0 / Rate;
                if (phase > 1.0) phase -= 1.0;
                sub += f0 * 0.5f / Rate;
                if (sub > 1.0) sub -= 1.0;
                float src = 0f;
                int maxH = Mathf.Min(24, (int)(7000f / f0));
                for (int h = 1; h <= maxH; h++) src += Mathf.Sin((float)(phase * h) * 2f * Mathf.PI) / (h * 0.9f + 0.4f);
                src *= 0.35f;
                if (p.growl > 0f) src *= 1f - p.growl * 0.45f * (0.5f + 0.5f * Mathf.Sin((float)sub * 2f * Mathf.PI));
                bool voiced = !(onset == 2 || onset == 3 || onset == 7) || i > onN;
                float noise = (float)rng.NextDouble() * 2f - 1f;
                float x = voiced ? src : 0f;
                float asp = noise * (p.breath + (i < onN && onset == 7 ? 0.6f : 0f));
                float y = res[0].Do(x + asp * 0.3f) * 1.0f + res[1].Do(x + asp * 0.5f) * 0.55f + res[2].Do(x + asp * 0.6f) * 0.28f;
                // consonant onsets
                if (i < onN)
                {
                    float on = i / (float)Mathf.Max(1, onN);
                    switch (onset)
                    {
                        case 1: y = y * on + noise * 0.25f * (1f - on); break;                                // voiced plosive
                        case 2: y = noise * 0.45f * (1f - on) * (on < 0.35f ? 1f : 0.4f); break;              // p/t/k burst
                        case 3: y = HiPass(ref hp1, noise) * 0.5f * Mathf.Sin(on * Mathf.PI); break;           // s/x/z hiss
                        case 4: y = y * on * 0.6f + noise * 0.18f * (1f - on); break;                          // f/v
                        case 5: y *= 0.45f; break;                                                             // nasal hum
                        case 7: y = aspRes[1].Do(noise) * 0.5f * (1f - on) + y * on; break;                    // h
                    }
                }
                if (p.nasal > 0f) y += Honk(ref honk, y, p.nasal);
                if (p.squeak > 0f) y += Mathf.Sin((float)(phase * 3.0) * 2f * Mathf.PI) * 0.08f * p.squeak;
                if (p.bubble > 0f && Mathf.Abs(k - bubbleAt) < 0.12f)
                {
                    float bk = (k - bubbleAt + 0.12f) / 0.24f;
                    y += Mathf.Sin(2f * Mathf.PI * (600f + 1800f * bk) * t) * 0.18f * p.bubble * Mathf.Sin(bk * Mathf.PI);
                }
                // envelope: quick attack, slight decay, soft release
                float env = Mathf.Clamp01(i / (0.005f * Rate)) * Mathf.Clamp01((n - i) / (0.022f * Rate)) * (1f - k * 0.25f);
                buf[i] = y * env;
            }
            hp1 = 0; honk = default;
            // normalise
            float peak = 0.0001f;
            foreach (var s in buf) peak = Mathf.Max(peak, Mathf.Abs(s));
            for (int i = 0; i < n; i++) buf[i] = buf[i] / peak * 0.8f;
            var clip = AudioClip.Create($"blip_{p.id}_{(char)('a' + letter)}", n, 1, Rate, false);
            clip.SetData(buf, 0);
            return clip;
        }

        static float hp1;
        static float HiPass(ref float state, float x)
        {
            float y = x - state;
            state = state * 0.2f + x * 0.8f;
            return y;
        }

        struct HonkState { public Reson r; public bool init; }
        static HonkState honk;
        static float Honk(ref HonkState h, float x, float amount)
        {
            if (!h.init) { h.r.Set(1500f, 90f); h.init = true; }
            return h.r.Do(x) * 0.6f * amount;
        }

        struct Reson
        {
            float a1, a2, b0, y1, y2;
            public void Set(float f, float bw)
            {
                float r = Mathf.Exp(-Mathf.PI * bw / Rate);
                float th = 2f * Mathf.PI * Mathf.Min(f, Rate * 0.45f) / Rate;
                a1 = 2f * r * Mathf.Cos(th);
                a2 = -r * r;
                b0 = (1f - r) * 1.6f;
            }
            public float Do(float x)
            {
                float y = b0 * x + a1 * y1 + a2 * y2;
                y2 = y1;
                y1 = y;
                return y;
            }
        }

        AudioSource Next()
        {
            var a = pool[next];
            next = (next + 1) % pool.Count;
            return a;
        }

        /// <summary>
        /// Voice one letter. contour: -1..1 intonation offset (questions rise, statements fall), emphasis: 0..1 louder/higher.
        /// Returns false (no sound) for non-letters or when rate-limited so blips don't pile up.
        /// </summary>
        public bool Speak(string voice, char c, float contour = 0f, float emphasis = 0f, bool force = false)
        {
            char l = char.ToLowerInvariant(c);
            if (l < 'a' || l > 'z') return false;
            var p = Profile(voice);
            float gap = 0.75f / p.speed;
            if (!force && Time.unscaledTime - lastBlip < gap) return false;
            lastBlip = Time.unscaledTime;
            var cl = Clips(p)[l - 'a'];
            var a = Next();
            a.clip = cl;
            a.pitch = Mathf.Clamp(1f + contour * 0.12f + emphasis * 0.08f + (Random.value - 0.5f) * 2f * p.pitchVar, 0.6f, 1.8f);
            a.volume = p.volume * Settings.Voice * (0.85f + emphasis * 0.3f);
            a.Play();
            return true;
        }

        /// <summary>A longer gibberish phrase (greetings, reactions): letters strung together with a pitch contour.</summary>
        public float Mumble(string voice, string text = null, float rise = 0f)
        {
            var p = Profile(voice);
            if (string.IsNullOrEmpty(text)) text = p.mumbles[Random.Range(0, p.mumbles.Length)];
            StartCoroutine(MumbleCo(p, text, rise));
            return text.Length / (p.speed * 0.55f);
        }

        System.Collections.IEnumerator MumbleCo(VoiceProfile p, string text, float rise)
        {
            var cl = Clips(p);
            int n = text.Length;
            bool exclaim = text.EndsWith("!"), ask = text.EndsWith("?");
            for (int i = 0; i < n; i++)
            {
                char l = char.ToLowerInvariant(text[i]);
                float k = i / Mathf.Max(1f, n - 1f);
                if (l < 'a' || l > 'z')
                {
                    yield return new WaitForSecondsRealtime(l == ' ' || l == '-' ? 0.07f : 0.02f);
                    continue;
                }
                var a = Next();
                a.clip = cl[l - 'a'];
                float contour = Mathf.Sin(k * Mathf.PI) * 0.5f + (ask ? k * 0.9f : exclaim ? 0.3f - k * 0.2f : -k * 0.4f) + rise;
                a.pitch = Mathf.Clamp(0.86f + contour * 0.14f + (Random.value - 0.5f) * p.pitchVar, 0.55f, 1.8f);
                a.volume = p.volume * Settings.Voice * (exclaim ? 1.1f : 0.95f);
                a.Play();
                yield return new WaitForSecondsRealtime(1.05f / (p.speed * 0.6f));
            }
        }
    }
}
