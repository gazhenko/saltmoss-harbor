using System;
using UnityEngine;

namespace Saltmoss
{
    public enum StopMotion { Twos = 12, Ones = 24, Off = 0 }

    /// <summary>
    /// The stop-motion clock. The world is "photographed" at <see cref="Fps"/> (12 = on twos): puppets, waves, smoke
    /// and particles only change on a step, and every step the clay surface is re-handled (boil). Gameplay, input and
    /// the camera run every frame, unless <see cref="FilmCamera"/> is on.
    /// </summary>
    public static class ClayClock
    {
        public static int Fps = 12;
        public static bool FilmCamera;
        public static float Boil = 1f;

        /// <summary>Game time of the current exposure (steps only when a new exposure is taken).</summary>
        public static float StepTime { get; private set; }
        /// <summary>Number of exposures so far.</summary>
        public static int Frame { get; private set; }
        /// <summary>True on the rendered frames where a new exposure was taken.</summary>
        public static bool SteppedThisFrame { get; private set; }
        /// <summary>Seconds between exposures (or this frame's delta when stop-motion is off).</summary>
        public static float StepDt { get; private set; } = 1f / 12f;
        public static event Action OnStep;

        static readonly int IdTime = Shader.PropertyToID("_ClayTime");
        static readonly int IdFrame = Shader.PropertyToID("_ClayFrame");
        static readonly int IdBoil = Shader.PropertyToID("_ClayBoil");
        static float lastStepAt = -1f;
        static int lastFrameCount = -1;

        public static void Apply(StopMotion mode, bool filmCamera)
        {
            Fps = (int)mode;
            FilmCamera = filmCamera && mode != StopMotion.Off;
        }

        internal static void Tick()
        {
            if (lastFrameCount == Time.frameCount) return;
            lastFrameCount = Time.frameCount;
            float t = Time.time;
            SteppedThisFrame = false;
            if (Fps <= 0)
            {
                StepDt = Time.deltaTime;
                StepTime = t;
                Frame++;
                SteppedThisFrame = true;
                // smooth mode is for motion sensitivity: no crawling surfaces either
                Shader.SetGlobalFloat(IdBoil, 0f);
            }
            else
            {
                float period = 1f / Fps;
                if (lastStepAt < 0f || t - lastStepAt >= period - 1e-4f || t < lastStepAt)
                {
                    StepDt = lastStepAt < 0f ? period : Mathf.Clamp(t - lastStepAt, 0f, period * 3f);
                    // stay phase-locked to the grid so exposures are evenly spaced
                    lastStepAt = lastStepAt < 0f || t < lastStepAt ? t : lastStepAt + period * Mathf.Floor((t - lastStepAt) / period + 1e-3f);
                    StepTime = lastStepAt;
                    Frame++;
                    SteppedThisFrame = true;
                }
                Shader.SetGlobalFloat(IdBoil, Boil);
            }
            if (SteppedThisFrame)
            {
                Shader.SetGlobalFloat(IdTime, StepTime);
                Shader.SetGlobalFloat(IdFrame, Frame % 4096);
                OnStep?.Invoke();
            }
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            lastStepAt = -1f;
            lastFrameCount = -1;
            Frame = 0;
            var go = new GameObject("ClayClock");
            UnityEngine.Object.DontDestroyOnLoad(go);
            go.hideFlags = HideFlags.HideInHierarchy;
            go.AddComponent<ClayClockDriver>();
        }
    }

    [DefaultExecutionOrder(-10000)]
    sealed class ClayClockDriver : MonoBehaviour
    {
        void Update() => ClayClock.Tick();
    }
}
