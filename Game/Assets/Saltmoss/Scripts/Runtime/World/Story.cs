using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// The first days' gentle tutorial as a chain of little tasks (shown on the HUD), then the harbour restoration
    /// goal; plus the morning routine (Marge's letters, Walter's forecast, Nell's sales while Pip was out).
    /// </summary>
    public class Story : MonoBehaviour
    {
        public static Story I { get; private set; }
        float seaHoursAway;
        bool wasAtSea;

        void Awake() { I = this; }

        void OnEnable() { GameFlow.DayStarted += Morning; }
        void OnDisable() { GameFlow.DayStarted -= Morning; }

        void Update()
        {
            HUD.Task = CurrentTask();
            // Nell keeps the counter while Pip is out at sea
            var boat = BoatController.I;
            bool atSea = boat != null && boat.Aboard;
            if (atSea && GameFlow.ClockRunning && !DialogueRunner.Active) seaHoursAway += Time.deltaTime * GameFlow.GameMinutesPerSecond / 60f;
            if (wasAtSea && !atSea && seaHoursAway > 0.5f && GameState.Flag("met_nell"))
            {
                ShopCounter.NellSales(seaHoursAway);
                seaHoursAway = 0f;
            }
            wasAtSea = atSea;
        }

        public static string CurrentTask()
        {
            bool F(string f) => GameState.Flag(f);
            string use = GameInput.Label(Bind.UseTool), act = GameInput.Label(Bind.Interact);
            if (!F("intro_done") && !F("met_walter")) return "Say hello to Walter at the harbour office.";
            if (!F("met_nell")) return "Visit the Salty Puffin on the pier and meet Nell.";
            if (!F("met_walter")) return "Ask Walter about the Sally Mae at the harbour office.";
            if (!F("dropped_pot")) return $"Board the Sally Mae and sail out past the harbour mouth. Drop a crab pot ({act}).";
            if (!F("caught_fish")) return $"Stop near a fish shadow and cast a line ({use}).";
            if (!F("hauled_pot")) return "Go back to your buoy and haul the pot.";
            if (!F("dredged")) return "Look for glimmering water and lower the dredge.";
            if (!F("unloaded_once")) return "Sail home and tie up at the berth.";
            if (!F("first_sale")) return "Open the Salty Puffin and serve a customer.";
            if (!F("met_inkwell")) return "Take your find to Professor Inkwell's museum on the beach.";
            if (GameState.Flag("ceremony_pending")) return "Walter's waiting for you on the pier!";
            return Restoration.Progress();
        }

        void Morning()
        {
            var D = GameState.D;
            AudioDirector.I?.Jingle("jingle_day_start");
            HUD.I?.Banner($"DAY {D.day}", GameFlow.WeatherName(D.weather) + (D.weather >= (int)Weather.Squalls ? " · rough out past the harbour" : ""));
            // a letter from Marge's post bag every other morning once you've met her
            if (GameState.Flag("met_marge") && D.day % 2 == 0) Letters.NewOrder();
        }
    }
}
