using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// The map: a paper chart of the town (on land) or of the sea (aboard and out of the harbour), opened with the Map
    /// control, with Pip, the Sally Mae, the crab pots and the places that matter marked on it; and, while sailing, a
    /// small round sea chart in the corner of the HUD. The charts are drawn by Tools/art/map_render.py.
    /// </summary>
    public class MapUI : MonoBehaviour
    {
        public static bool Showing { get; private set; }
        static MapUI inst;

        // world rects of the two charts (Tools/art/map_render.py RECTS)
        static readonly Rect TownRect = Rect.MinMaxRect(-160f, -64f, 160f, 96f);
        static readonly Rect SeaRect = Rect.MinMaxRect(-960f, -105f, 960f, 855f);
        const float MiniSize = 280f, MiniMetres = 420f;

        class Mark { public RectTransform rt; public Vector3 world; public bool town, sea; }

        Canvas canvas, miniCanvas;
        RectTransform chart, miniChart;
        Image chartImg;
        TextMeshProUGUI title, hint;
        Button townTab, seaTab;
        bool sea;
        RectTransform pip, boat, boatArrow, miniBoat;
        readonly List<Mark> places = new List<Mark>();
        readonly List<RectTransform> pots = new List<RectTransform>(), miniPots = new List<RectTransform>();
        CanvasGroup miniGroup;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (inst != null) return;
            var go = new GameObject("MapUI");
            DontDestroyOnLoad(go);
            inst = go.AddComponent<MapUI>();
        }

        // ------------------------------------------------------------------ build

        void Build()
        {
            canvas = ClayUI.Canvas("MapCanvas", 68, transform);
            var dim = ClayUI.Fill("Dim", canvas.transform);
            dim.gameObject.AddComponent<Image>().color = new Color(0.1f, 0.08f, 0.06f, 0.55f);
            var frame = ClayUI.Panel("Frame", canvas.transform, "panel_sand", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1760f, 1010f));
            title = ClayUI.Text("Title", frame.transform, "", 46f, ClayUI.Red, TextAlignmentOptions.TopLeft, true);
            title.margin = new Vector4(50, 24, 0, 0);
            hint = ClayUI.Text("Hint", frame.transform, "", 24f, ClayUI.Muted, TextAlignmentOptions.Bottom);
            hint.margin = new Vector4(0, 0, 0, 18);
            townTab = ClayUI.Button("TownTab", frame.transform, "Town", new Vector2(1f, 1f), new Vector2(-380f, -58f), new Vector2(200f, 64f), () => Show(false), 26f);
            seaTab = ClayUI.Button("SeaTab", frame.transform, "Sea", new Vector2(1f, 1f), new Vector2(-160f, -58f), new Vector2(200f, 64f), () => Show(true), 26f);
            var holder = ClayUI.Rect("Holder", frame.transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0f, -16f), new Vector2(1680f, 850f));
            var img = new GameObject("Chart", typeof(RectTransform)).AddComponent<Image>();
            img.transform.SetParent(holder, false);
            img.raycastTarget = false;
            chartImg = img;
            chart = img.rectTransform;

            pip = Arrow(chart, "Pip", new Color(0.86f, 0.3f, 0.22f), 46f);
            // the boat: a turning arrow with a label that stays level
            boat = ClayUI.Rect("SallyMae", chart, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(10f, 10f));
            boatArrow = Arrow(boat, "Arrow", new Color(0.2f, 0.36f, 0.5f), 38f);
            Label(boat, "the Sally Mae", 20f, new Vector2(0f, -34f));

            // places: town names only on the town chart, sea names only on the sea chart
            var refs = WorldRefs.I;
            var b = BoatController.I;
            if (refs != null)
            {
                // label offsets keep neighbouring names apart
                Place("Pip's House", refs.pipDoor, new Vector2(46f, 18f));
                Place("The Salty Puffin", refs.shopStand, new Vector2(64f, 20f));
                Place("Harbour Office", refs.board, new Vector2(62f, -20f));
                Place("Post Office", refs.postOffice, new Vector2(-30f, -24f));
                Place("Tidewrack Museum", refs.museumDoor, new Vector2(-84f, 22f));
                Place("Lighthouse", refs.lighthouse, new Vector2(0f, 24f));
            }
            if (b != null)
            {
                PlaceAt("Berth", b.berthPos, true, false, offset: new Vector2(44f, 0f));
                var mouth = new Vector3(b.harbourMouth.x, 0f, b.harbourMouth.y);
                PlaceAt("Harbour mouth", mouth + new Vector3(0f, 0f, 9f), true, false);
                PlaceAt("Saltmoss Harbor", mouth + new Vector3(0f, 0f, -70f), false, true, 30f, false);
                PlaceAt("The Shallows", mouth + new Vector3(0f, 0f, 100f), false, true, 30f, false);
                PlaceAt("Kelp Reach", mouth + new Vector3(0f, 0f, 270f), false, true, 30f, false);
                PlaceAt("The Grey Deep", mouth + new Vector3(0f, 0f, 560f), false, true, 30f, false);
                PlaceAt("Fog bank", mouth + new Vector3(-560f, 0f, 610f), false, true, 24f, false);
            }
            if (Dredge.I != null) PlaceAt("Old wreck", Dredge.I.wreck, false, true);
            pip.SetAsLastSibling();
            canvas.gameObject.SetActive(false);
        }

        void BuildMini()
        {
            miniCanvas = ClayUI.Canvas("MiniMapCanvas", 12, transform);
            miniGroup = miniCanvas.gameObject.AddComponent<CanvasGroup>();
            miniGroup.alpha = 0f;
            // a little framed chart in the corner, clipped by rectangle (no stencil)
            var ring = ClayUI.Panel("Frame", miniCanvas.transform, "panel_sand", new Vector2(0f, 0f), new Vector2(22f, 22f), new Vector2(MiniSize + 64f, MiniSize + 64f), null, new Vector2(0f, 0f));
            var face = ClayUI.Rect("View", ring.transform, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(MiniSize, MiniSize));
            face.gameObject.AddComponent<RectMask2D>().softness = new Vector2Int(4, 4);
            var img = new GameObject("Chart", typeof(RectTransform)).AddComponent<Image>();
            img.transform.SetParent(face, false);
            img.raycastTarget = false;
            img.sprite = UIBank.I.Get("map_sea");
            miniChart = img.rectTransform;
            float k = MiniSize / MiniMetres;
            miniChart.sizeDelta = new Vector2(SeaRect.width * k, SeaRect.height * k);
            miniBoat = Arrow(face, "Boat", new Color(0.86f, 0.3f, 0.22f), 30f);
            var n = ClayUI.Text("N", ring.transform, "N", 26f, ClayUI.Cream, TextAlignmentOptions.Top, true);
            n.margin = new Vector4(0, -6, 0, 0);
            n.outlineWidth = 0.25f;
            n.outlineColor = new Color32(0x3a, 0x2a, 0x22, 255);
        }

        RectTransform Arrow(Transform parent, string name, Color c, float size)
        {
            var a = ClayUI.Panel(name, parent, "arrow", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(size, size), c);
            a.raycastTarget = false;
            return a.rectTransform;
        }

        RectTransform Dot(Transform parent, Color c, float size)
        {
            var ring = ClayUI.Panel("Pot", parent, "dot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(size + 6f, size + 6f), new Color(0.33f, 0.25f, 0.19f));
            ClayUI.Panel("Fill", ring.transform, "dot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(size, size), c);
            return ring.rectTransform;
        }

        void Label(RectTransform under, string text, float size, Vector2 offset)
        {
            var t = ClayUI.Text("Label", under, text, size, ClayUI.Ink, TextAlignmentOptions.Center, true);
            var rt = t.rectTransform;
            rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(360f, 40f);
            rt.anchoredPosition = offset;
            rt.localRotation = Quaternion.identity;
            t.textWrappingMode = TextWrappingModes.NoWrap;
            t.outlineWidth = 0.22f;
            t.outlineColor = new Color32(0xf4, 0xec, 0xd8, 255);
        }

        void Place(string name, Transform at, Vector2 offset)
        {
            if (at != null) PlaceAt(name, at.position, true, false, offset: offset);
        }

        void PlaceAt(string name, Vector3 world, bool town, bool seaChart, float size = 22f, bool pin = true, Vector2? offset = null)
        {
            var rt = ClayUI.Rect(name, chart, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(10f, 10f));
            if (pin)
            {
                var d = ClayUI.Panel("Pin", rt, "dot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(18f, 18f), new Color(0.33f, 0.25f, 0.19f));
                ClayUI.Panel("Fill", d.transform, "dot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(11f, 11f), new Color(0.97f, 0.9f, 0.7f));
            }
            Label(rt, name, size, offset ?? (pin ? new Vector2(0f, 24f) : Vector2.zero));
            places.Add(new Mark { rt = rt, world = world, town = town, sea = seaChart });
        }

        // ------------------------------------------------------------------ open / close

        public static void Toggle()
        {
            if (inst == null) return;
            if (inst.canvas == null) inst.Build();
            if (Showing) inst.Close(); else inst.Open();
        }

        /// <summary>Verification captures (-map town|sea): open on that chart.</summary>
        public static void OpenForCapture(bool seaChart)
        {
            if (inst == null) return;
            if (inst.canvas == null) inst.Build();
            if (!Showing) inst.Open();
            inst.Show(seaChart);
        }

        void Open()
        {
            Showing = true;
            canvas.gameObject.SetActive(true);
            if (GameFlow.I != null) GameFlow.I.InMenu = true;
            PlayerController.LockCount++;
            AudioDirector.UI("page_turn");
            var b = BoatController.I;
            Show(b != null && b.Aboard && !b.InHarbour);
        }

        void Close()
        {
            Showing = false;
            canvas.gameObject.SetActive(false);
            if (GameFlow.I != null) GameFlow.I.InMenu = false;
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            AudioDirector.UI("ui_close");
        }

        void Show(bool seaChart)
        {
            if (sea != seaChart && Showing) AudioDirector.UI("page_turn", 0.6f);
            sea = seaChart;
            title.text = sea ? "Sea Chart" : "Saltmoss Harbor";
            chartImg.sprite = UIBank.I.Get(sea ? "map_sea" : "map_town");
            var r = sea ? SeaRect : TownRect;
            // fit the chart in the frame, keeping its shape
            var avail = new Vector2(1680f, 850f);
            float s = Mathf.Min(avail.x / r.width, avail.y / r.height);
            chart.sizeDelta = new Vector2(r.width * s, r.height * s);
            townTab.GetComponent<Image>().sprite = UIBank.I.Get(sea ? "button" : "button_on");
            seaTab.GetComponent<Image>().sprite = UIBank.I.Get(sea ? "button_on" : "button");
            hint.text = $"{GameInput.Label(Bind.Map)}  close      {(GameInput.UsingGamepad ? "D-PAD" : "← →")}  town / sea";
            foreach (var m in places) m.rt.gameObject.SetActive(sea ? m.sea : m.town);
            Refresh();
        }

        // ------------------------------------------------------------------ live

        static Vector2 Uv(Rect r, Vector3 w) => new Vector2((w.x - r.xMin) / r.width, (w.z - r.yMin) / r.height);

        void Put(RectTransform rt, Rect r, Vector3 w, float yaw = float.NaN)
        {
            var uv = Uv(r, w);
            bool inside = uv.x >= 0f && uv.x <= 1f && uv.y >= 0f && uv.y <= 1f;
            rt.gameObject.SetActive(inside);
            if (!inside) return;
            rt.anchorMin = rt.anchorMax = uv;
            rt.anchoredPosition = Vector2.zero;
            if (!float.IsNaN(yaw)) rt.localRotation = Quaternion.Euler(0f, 0f, -yaw);
        }

        void Refresh()
        {
            var r = sea ? SeaRect : TownRect;
            var b = BoatController.I;
            var p = PlayerController.I;
            bool aboard = b != null && b.Aboard;
            if (p != null) Put(pip, r, aboard ? b.transform.position : p.transform.position, aboard ? b.transform.eulerAngles.y : p.transform.eulerAngles.y);
            if (b != null)
            {
                Put(boat, r, b.transform.position);
                boatArrow.localRotation = Quaternion.Euler(0f, 0f, -b.transform.eulerAngles.y);
                if (aboard) boat.gameObject.SetActive(false);
            }
            foreach (var m in places) if (sea ? m.sea : m.town) Put(m.rt, r, m.world);
            Pots(chart, pots, r, 22f, null);
            boat.SetAsLastSibling();
            pip.SetAsLastSibling();
        }

        void Pots(RectTransform parent, List<RectTransform> list, Rect r, float size, System.Func<Vector3, Vector2> place)
        {
            var all = GameState.D.pots;
            while (list.Count < all.Count) list.Add(Dot(parent, Color.white, size));
            for (int i = 0; i < list.Count; i++)
            {
                bool on = i < all.Count;
                list[i].gameObject.SetActive(on);
                if (!on) continue;
                var s = all[i];
                list[i].GetChild(0).GetComponent<Image>().color = CrabPots.BuoyColour(s.colour);
                var w = new Vector3(s.x, 0f, s.z);
                if (place == null) Put(list[i], r, w);
                else { list[i].anchorMin = list[i].anchorMax = new Vector2(0.5f, 0.5f); list[i].anchoredPosition = place(w); }
            }
        }

        void UpdateMini()
        {
            var b = BoatController.I;
            bool want = b != null && b.Aboard && !b.Docked && !Showing && !HUD.ForceHidden && !DialogueRunner.Active
                        && !TitleScreen.Showing && !CatchReveal.Showing && !(GameFlow.I != null && GameFlow.I.InMenu);
            if (want && !b.InHarbour && !GameState.Flag("map_tip"))
            {
                GameState.SetFlag("map_tip");
                GameState.Say($"Press {GameInput.Label(Bind.Map)} for the sea chart: your pots, the fishing grounds and the way home.");
            }
            if (miniCanvas == null) { if (!want) return; BuildMini(); }
            miniGroup.alpha = Mathf.MoveTowards(miniGroup.alpha, want ? 1f : 0f, Time.unscaledDeltaTime * 4f);
            if (miniGroup.alpha <= 0f) return;
            // north-up chart sliding under the boat, which stays in the middle and turns
            float k = MiniSize / MiniMetres;
            var c = SeaRect.center;
            var bp = b.transform.position;
            miniChart.anchoredPosition = new Vector2((c.x - bp.x) * k, (c.y - bp.z) * k);
            miniBoat.localRotation = Quaternion.Euler(0f, 0f, -b.transform.eulerAngles.y);
            Pots((RectTransform)miniBoat.parent, miniPots, SeaRect, 14f, w => new Vector2((w.x - bp.x) * k, (w.z - bp.z) * k));
            miniBoat.SetAsLastSibling();
        }

        void Update()
        {
            UpdateMini();
            if (TitleScreen.Showing || CatchReveal.Showing || DialogueRunner.Active || ServeUI.Showing || PauseMenu.Showing || JournalUI.Showing) return;
            if (ShopCounter.I != null && ShopCounter.I.Open) return;
            if (GameInput.Map.WasPressedThisFrame() || (Showing && GameInput.Back.WasPressedThisFrame())) Toggle();
            if (!Showing) return;
            if (GameInput.NavLeft.WasPressedThisFrame() && sea) Show(false);
            else if (GameInput.NavRight.WasPressedThisFrame() && !sea) Show(true);
            Refresh();
        }
    }
}
