using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Scene bootstrap: settings, input, the always-on UI layers, then the title screen (or straight into play for
    /// verification captures and the trailer). Places Pip and the Sally Mae for a new game or a loaded save.
    /// </summary>
    [DefaultExecutionOrder(-500)]
    public class GameBoot : MonoBehaviour
    {
        public static GameBoot I { get; private set; }
        public PlayerController player;
        public BoatController boat;
        public bool skipTitle;

        void Awake()
        {
            I = this;
            Settings.Load();
            GameInput.Init();
            Application.targetFrameRate = -1;
            HUD.Ensure();
            CatchReveal.Ensure();
            DialogueUI.Ensure();
            PortraitStage.Ensure();
            ItemStage.Ensure();
            DialogueScript.Load();
        }

        void Start()
        {
            if (player != null) DialogueRunner.Register("pip", player.transform, player.face, player.anim);
            bool direct = skipTitle || CommandLine.Has("-play") || CommandLine.Has("-trailer") || CommandLine.Has("-cam");
            if (direct)
            {
                if (CommandLine.Has("-continue") && GameState.HasSave) GameState.Load(); else GameState.New();
                if (CommandLine.Has("-day")) GameState.D.day = (int)CommandLine.GetFloat("-day", 1);
                if (CommandLine.Has("-money")) GameState.D.money = (int)CommandLine.GetFloat("-money", 120);
                if (CommandLine.Has("-flags")) foreach (var f in CommandLine.Get("-flags").Split(',')) GameState.SetFlag(f);
                if (CommandLine.Has("-weather")) GameState.D.weather = (int)CommandLine.GetFloat("-weather", 0);
                if (CommandLine.Has("-hour")) GameState.D.hour = CommandLine.GetFloat("-hour", 9f);
                if (CommandLine.Has("-restoration")) { GameState.D.restoration = (int)CommandLine.GetFloat("-restoration", 0); }
                PlaceForStart(!CommandLine.Has("-continue"));
                GameFlow.ClockRunning = !CommandLine.Has("-freezeClock");
            }
            else TitleScreen.Show();
        }

        public void PlaceForStart(bool fresh)
        {
            var refs = WorldRefs.I;
            var spot = fresh ? refs?.playerSpawn : refs?.pipDoor;
            if (player != null && spot != null) player.Teleport(spot.position, spot.eulerAngles.y);
            if (boat != null) boat.ForceDock();
            CrabPots.I?.Resync();
            Museum.I?.Refresh();
            ShopCounter.I?.RefreshDisplay();
            Restoration.I?.Apply();
            PotsVisual.Refresh();
            if (DayCycle.I != null) DayCycle.I.hour = GameState.D.hour;
            if (CameraRig.I != null && player != null)
            {
                CameraRig.I.target = player.transform;
                CameraRig.I.boatMode = false;
                CameraRig.I.SnapBehindTarget();
            }
            if (GameFlow.I != null) GameFlow.I.place = GameFlow.Place.Town;
        }
    }
}
