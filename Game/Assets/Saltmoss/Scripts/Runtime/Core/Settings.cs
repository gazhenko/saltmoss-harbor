using System;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Player options, persisted in PlayerPrefs and applied to the clock, quality and audio.</summary>
    public static class Settings
    {
        public static float Master = 0.9f, Music = 0.7f, Sfx = 0.85f, Voice = 0.8f, Ambience = 0.8f;
        public static StopMotion Motion = StopMotion.Twos;
        public static bool FilmCamera;
        public static bool DepthOfField = true;
        public static float TextSpeed = 1f;          // 0.5 .. 2
        public static float LookSensitivity = 1f;
        public static bool InvertY;
        public static int Quality = 2;
        public static bool Fullscreen = true;
        public static bool ShowHints = true;
        public static bool Vibration = true;
        public static float StickDeadzone = 0.15f;
        /// <summary>0 = automatic button labels, 1 Xbox, 2 PlayStation, 3 Nintendo.</summary>
        public static int PadLabels;
        public static event Action Changed;

        const string Key = "saltmoss_settings_v1";

        [Serializable]
        class Data
        {
            public float master = 0.9f, music = 0.7f, sfx = 0.85f, voice = 0.8f, ambience = 0.8f;
            public int motion = 12;
            public bool film, dof = true, invertY, fullscreen = true, hints = true;
            public float textSpeed = 1f, look = 1f;
            public int quality = 2;
        }

        public static void Load()
        {
            var json = PlayerPrefs.GetString(Key, "");
            var d = string.IsNullOrEmpty(json) ? new Data() : JsonUtility.FromJson<Data>(json) ?? new Data();
            Master = d.master; Music = d.music; Sfx = d.sfx; Voice = d.voice; Ambience = d.ambience;
            Motion = d.motion == 24 ? StopMotion.Ones : d.motion == 0 ? StopMotion.Off : StopMotion.Twos;
            FilmCamera = d.film; DepthOfField = d.dof; InvertY = d.invertY; Fullscreen = d.fullscreen; ShowHints = d.hints;
            TextSpeed = Mathf.Clamp(d.textSpeed, 0.5f, 2f); LookSensitivity = Mathf.Clamp(d.look, 0.3f, 3f);
            Quality = Mathf.Clamp(d.quality, 0, 2);
            Apply(false);
        }

        public static void Save()
        {
            var d = new Data
            {
                master = Master, music = Music, sfx = Sfx, voice = Voice, ambience = Ambience, motion = (int)Motion,
                film = FilmCamera, dof = DepthOfField, invertY = InvertY, fullscreen = Fullscreen, hints = ShowHints,
                textSpeed = TextSpeed, look = LookSensitivity, quality = Quality,
            };
            PlayerPrefs.SetString(Key, JsonUtility.ToJson(d));
            PlayerPrefs.Save();
        }

        public static void Apply(bool save = true)
        {
            ClayClock.Apply(Motion, FilmCamera);
            if (QualitySettings.GetQualityLevel() != Quality) QualitySettings.SetQualityLevel(Quality, true);
            if (!Application.isEditor && Screen.fullScreen != Fullscreen)
                Screen.fullScreenMode = Fullscreen ? FullScreenMode.FullScreenWindow : FullScreenMode.Windowed;
            AudioListener.volume = Master;
            if (save) Save();
            Changed?.Invoke();
        }
    }
}
