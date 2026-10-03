using System;
using System.Collections.Generic;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// The game's director: the clock (a day runs 06:00–24:00 in twelve real minutes), weather for the day, music and
    /// ambience by where Pip is, and the hub that dialogue scripts call into (!event …) to open shops, the museum,
    /// sleep, letters and so on. UIs register handlers here so the director stays small.
    /// </summary>
    public class GameFlow : MonoBehaviour
    {
        public static GameFlow I { get; private set; }
        public const float GameMinutesPerSecond = 1.5f;

        public static bool ClockRunning = true;
        public static event Action DayStarted;
        public static event Action<float> HourChanged;

        static readonly Dictionary<string, Action<string[], Action>> handlers = new Dictionary<string, Action<string[], Action>>();

        /// <summary>Register an !event handler (UIs, systems). The handler must call done when finished.</summary>
        public static void On(string name, Action<string[], Action> handler) => handlers[name] = handler;

        public static void Event(string name, string[] args, Action done)
        {
            if (name != null && handlers.TryGetValue(name, out var h))
            {
                try { h(args, done); }
                catch (Exception e) { Debug.LogException(e); done?.Invoke(); }
                return;
            }
            Debug.LogWarning("[GameFlow] no handler for event " + name);
            done?.Invoke();
        }

        public enum Place { Town, Sea, Shop, Museum }
        public Place place = Place.Town;
        public bool InMenu;

        void Awake() { I = this; }

        void Update()
        {
            var D = GameState.D;
            if (ClockRunning && !DialogueRunner.Active && !InMenu && Time.timeScale > 0f)
            {
                float before = D.hour;
                D.hour += Time.deltaTime * GameMinutesPerSecond / 60f;
                if (Mathf.FloorToInt(before) != Mathf.FloorToInt(D.hour)) HourChanged?.Invoke(D.hour);
                if (D.hour >= 24f) PassOut();
            }
            var dc = DayCycle.I;
            if (dc != null && !dc.frozen) dc.hour = D.hour;
            UpdateMood();
        }

        float moodTimer;

        void UpdateMood()
        {
            moodTimer -= Time.unscaledDeltaTime;
            if (moodTimer > 0f || AudioDirector.I == null) return;
            moodTimer = 1f;
            var D = GameState.D;
            bool night = D.hour >= 20f || D.hour < 6f;
            var w = (Weather)D.weather;
            float rough = 0f;
            var p = PlayerController.I;
            if (p != null && SeaState.I != null) rough = SeaState.I.Roughness01(p.transform.position);
            switch (place)
            {
                case Place.Shop: AudioDirector.I.Music("shop"); AudioDirector.I.Ambience("amb_harbor_day", w >= Weather.Showers ? "amb_rain_roof" : null); break;
                case Place.Museum: AudioDirector.I.Music("museum"); AudioDirector.I.Ambience("amb_shop"); break;
                case Place.Sea:
                    bool stormy = (w >= Weather.Squalls && rough > 0.3f) || rough > 0.75f;
                    AudioDirector.I.Music(stormy ? "sea_storm" : "sea_calm");
                    AudioDirector.I.Ambience(stormy ? "amb_sea_storm" : "amb_sea_calm", w >= Weather.Showers ? "amb_rain_roof" : null);
                    AudioDirector.I.StormAmount(rough);
                    break;
                default:
                    AudioDirector.I.Music(night ? "town_night" : "town_day");
                    AudioDirector.I.Ambience(night ? "amb_harbor_night" : "amb_harbor_day", w >= Weather.Showers ? "amb_rain_roof" : null);
                    break;
            }
        }

        /// <summary>Midnight: Pip nods off wherever they are and wakes at home.</summary>
        void PassOut()
        {
            GameState.Say("Pip's too sleepy to carry on… Off to bed!");
            Sleep(null);
        }

        public static event Action<Action> SleepRequested;

        public static void Sleep(Action done)
        {
            if (SleepRequested != null) SleepRequested(done);
            else { NewDay(); done?.Invoke(); }
        }

        /// <summary>Advance to the next morning: weather, pots soak, Nell's sales, autosave.</summary>
        public static void NewDay()
        {
            var D = GameState.D;
            D.day++;
            D.hour = 6.25f;
            D.weather = D.forecast;
            D.forecast = RollWeather(D.day + 1);
            D.nellSalesToday = 0f;
            DayStarted?.Invoke();
            GameState.Save();
        }

        public static int RollWeather(int day)
        {
            // a gentle first few days, then a mix with a storm now and then
            var r = new System.Random(day * 7919 + 13);
            if (day <= 2) return (int)(day == 1 ? Weather.Clear : Weather.Breezy);
            double x = r.NextDouble();
            if (x < 0.32) return (int)Weather.Clear;
            if (x < 0.55) return (int)Weather.Breezy;
            if (x < 0.7) return (int)Weather.Showers;
            if (x < 0.8) return (int)Weather.Fog;
            if (x < 0.92) return (int)Weather.Squalls;
            return (int)Weather.Storm;
        }

        public static string WeatherName(int w) => ((Weather)w) switch
        {
            Weather.Clear => "Clear skies",
            Weather.Breezy => "Breezy",
            Weather.Showers => "Showers",
            Weather.Fog => "Fog",
            Weather.Squalls => "Squalls",
            _ => "Storm",
        };

        public static string Clock(float hour)
        {
            int h = Mathf.FloorToInt(hour) % 24;
            int m = Mathf.FloorToInt((hour - Mathf.Floor(hour)) * 60f / 10f) * 10;
            string ap = h < 12 ? "am" : "pm";
            int h12 = h % 12 == 0 ? 12 : h % 12;
            return $"{h12}:{m:00}{ap}";
        }
    }
}
