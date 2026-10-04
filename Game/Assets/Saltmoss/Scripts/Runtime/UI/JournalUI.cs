using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// Pip's journal: the collection book (fish, crabs, treasures — silhouettes until found, a museum stamp once
    /// donated), what's in the hold and the cold store, letters, and how the harbour restoration is going.
    /// </summary>
    public class JournalUI : MonoBehaviour
    {
        public static bool Showing { get; private set; }
        static JournalUI inst;
        Canvas canvas;
        RectTransform page;
        TextMeshProUGUI title, detail;
        readonly List<Button> tabs = new List<Button>();
        readonly List<GameObject> content = new List<GameObject>();
        int tab;
        static readonly string[] TabNames = { "Fish", "Crabs", "Treasures", "Hold & Shop", "Letters" };

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (inst != null) return;
            var go = new GameObject("JournalUI");
            DontDestroyOnLoad(go);
            inst = go.AddComponent<JournalUI>();
        }

        void Build()
        {
            canvas = ClayUI.Canvas("JournalCanvas", 70, transform);
            var dim = ClayUI.Fill("Dim", canvas.transform);
            dim.gameObject.AddComponent<Image>().color = new Color(0.1f, 0.08f, 0.06f, 0.5f);
            var book = ClayUI.Panel("Book", canvas.transform, "panel_sand", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1640f, 920f));
            var paper = ClayUI.Panel("Paper", book.transform, "panel_paper", new Vector2(0.5f, 0.5f), new Vector2(0f, -40f), new Vector2(1560f, 780f));
            page = paper.rectTransform;
            title = ClayUI.Text("Title", book.transform, "Pip's Journal", 46f, ClayUI.Red, TextAlignmentOptions.TopLeft, true);
            title.margin = new Vector4(50, 26, 0, 0);
            detail = ClayUI.Text("Detail", paper.transform, "", 26f, ClayUI.Ink, TextAlignmentOptions.BottomLeft);
            detail.margin = new Vector4(40, 0, 40, 24);
            for (int i = 0; i < TabNames.Length; i++)
            {
                int k = i;
                var b = ClayUI.Button("Tab" + i, book.transform, TabNames[i], new Vector2(1f, 1f), new Vector2(-1130f + i * 226f, -60f), new Vector2(214f, 70f), () => Show(k), 26f);
                tabs.Add(b);
            }
            canvas.gameObject.SetActive(false);
        }

        public static void Toggle()
        {
            if (inst == null) return;
            if (inst.canvas == null) inst.Build();
            if (Showing) inst.Close(); else inst.Open();
        }

        void Open()
        {
            Showing = true;
            canvas.gameObject.SetActive(true);
            if (GameFlow.I != null) GameFlow.I.InMenu = true;
            PlayerController.LockCount++;
            AudioDirector.UI("page_turn");
            Show(tab);
        }

        void Close()
        {
            Showing = false;
            canvas.gameObject.SetActive(false);
            if (GameFlow.I != null) GameFlow.I.InMenu = false;
            PlayerController.LockCount = Mathf.Max(0, PlayerController.LockCount - 1);
            AudioDirector.UI("ui_close");
        }

        void Show(int t)
        {
            tab = t;
            foreach (var c in content) Destroy(c);
            content.Clear();
            for (int i = 0; i < tabs.Count; i++) tabs[i].GetComponent<Image>().sprite = UIBank.I.Get(i == t ? "button_on" : "button");
            detail.text = "";
            AudioDirector.UI("page_turn", 0.5f);
            if (t <= 2) Collection(t == 0 ? Kind.Fish : t == 1 ? Kind.Crab : Kind.Treasure);
            else if (t == 3) Stores();
            else LettersPage();
            ClayUI.Select(tabs[t]);
        }

        RectTransform Grid(int cols, Vector2 cell)
        {
            var g = ClayUI.Rect("Grid", page, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -30f), new Vector2(1500f, 640f), new Vector2(0.5f, 1f));
            var gl = g.gameObject.AddComponent<GridLayoutGroup>();
            gl.cellSize = cell;
            gl.spacing = new Vector2(14f, 14f);
            gl.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            gl.constraintCount = cols;
            gl.childAlignment = TextAnchor.UpperCenter;
            content.Add(g.gameObject);
            return g;
        }

        void Collection(Kind kind)
        {
            var D = GameState.D;
            var g = Grid(8, new Vector2(170f, 190f));
            int found = 0, total = 0, donated = 0;
            foreach (var d in Catalog.OfKind(kind))
            {
                total++;
                bool seen = D.discovered.Contains(d.id);
                bool don = D.donated.Contains(d.id);
                if (seen) found++;
                if (don) donated++;
                var cell = ClayUI.Panel("Cell", g, "slot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(170f, 190f));
                cell.raycastTarget = true;
                var b = cell.gameObject.AddComponent<Button>();
                var def = d;
                b.onClick.AddListener(() => detail.text = seen ? $"<b>{def.name}</b>{(def.Sellable ? $" · {def.price} SD" : "")} — {Where(def)}\n<i>{(don ? def.lore : def.caught)}</i>" : "<b>???</b> — " + Hint(def));
                var nav = b.navigation; nav.mode = Navigation.Mode.Automatic; b.navigation = nav;
                var ic = ClayUI.Panel("Icon", cell.transform, null, new Vector2(0.5f, 0.58f), Vector2.zero, new Vector2(128f, 128f));
                ic.sprite = ItemStage.Ensure().Icon(d.id);
                ic.preserveAspect = true;
                ic.color = seen ? Color.white : new Color(0.25f, 0.2f, 0.18f, 0.55f);
                var t = ClayUI.Text("Label", cell.transform, seen ? d.name : "???", 20f, ClayUI.Ink, TextAlignmentOptions.Bottom);
                t.margin = new Vector4(6, 0, 6, 10);
                if (don)
                {
                    var st = ClayUI.Panel("Stamp", cell.transform, "stamp", new Vector2(1f, 1f), new Vector2(-28f, -28f), new Vector2(54f, 54f));
                    st.rectTransform.localRotation = Quaternion.Euler(0, 0, 12f);
                }
            }
            title.text = "Pip's Journal";
            detail.text = $"{found}/{total} found · {donated} in the museum · select one to read about it";
        }

        static string Where(ItemDef d)
        {
            var parts = new List<string>();
            if ((d.zones & ZoneMask.Shallows) != 0) parts.Add("the Shallows");
            if ((d.zones & ZoneMask.Kelp) != 0) parts.Add("Kelp Reach");
            if ((d.zones & ZoneMask.Deep) != 0) parts.Add("the Grey Deep");
            string w = string.Join(", ", parts);
            if (d.night) w += ", at night";
            if (d.storm) w += ", in a storm";
            return w;
        }

        static string Hint(ItemDef d)
        {
            string how = d.kind == Kind.Fish ? "Caught on a line" : d.kind == Kind.Crab ? "Hauled in a crab pot" : "Dredged from the seabed";
            return $"{how} in {Where(d)}.";
        }

        void Stores()
        {
            var D = GameState.D;
            title.text = "Pip's Journal";
            var g = Grid(8, new Vector2(170f, 190f));
            void Add(List<Stack> list, string where)
            {
                var ids = new List<string>();
                foreach (var s in list) if (!ids.Contains(s.id)) ids.Add(s.id);
                foreach (var id in ids)
                {
                    var d = Catalog.Get(id);
                    var cell = ClayUI.Panel("Cell", g, "slot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(170f, 190f));
                    var ic = ClayUI.Panel("Icon", cell.transform, null, new Vector2(0.5f, 0.58f), Vector2.zero, new Vector2(128f, 128f));
                    ic.sprite = ItemStage.Ensure().Icon(id);
                    ic.preserveAspect = true;
                    ic.color = Color.white;
                    var t = ClayUI.Text("Label", cell.transform, $"{d.name} ×{GameState.Count(list, id)}\n<size=75%><color=#7a6858>{where}</color></size>", 19f, ClayUI.Ink, TextAlignmentOptions.Bottom);
                    t.margin = new Vector4(6, 0, 6, 8);
                }
            }
            Add(D.hold, "hold");
            Add(D.stock, "cold store");
            Add(D.pocket, "pocket");
            detail.text = $"Hold {GameState.Count(D.hold)}/{GameState.HoldCapacity} · Cold store {GameState.Count(D.stock)} · Pocket {GameState.Count(D.pocket)} — " + Restoration.Progress().Replace("\n", " — ");
        }

        void LettersPage()
        {
            var orders = Letters.Open();
            title.text = "Pip's Journal";
            var col = ClayUI.Rect("Letters", page, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -40f), new Vector2(1400f, 600f), new Vector2(0.5f, 1f));
            var vl = col.gameObject.AddComponent<VerticalLayoutGroup>();
            vl.spacing = 16f;
            vl.childControlHeight = false;
            vl.childForceExpandHeight = false;
            content.Add(col.gameObject);
            if (orders.Count == 0)
            {
                var t = ClayUI.Text("None", col, "No letters waiting. Marge sorts the post every other morning.", 32f, ClayUI.Ink, TextAlignmentOptions.Center);
                t.gameObject.AddComponent<LayoutElement>().preferredHeight = 120f;
            }
            foreach (var o in orders)
            {
                var row = ClayUI.Panel("Letter", col, "panel_cream", new Vector2(0.5f, 1f), Vector2.zero, new Vector2(1400f, 110f));
                row.gameObject.AddComponent<LayoutElement>().preferredHeight = 110f;
                bool late = GameState.D.day > o.due;
                var t = ClayUI.Text("Text", row.transform, $"<b>{o.from}</b> would like <b>{o.count} × {o.Def?.name}</b> by day {o.due}{(late ? " <color=#c24a3a>(late — they'll still pay)</color>" : "")}. Reward {o.reward} SD.", 28f, ClayUI.Ink, TextAlignmentOptions.Left);
                t.margin = new Vector4(30, 12, 30, 16);
            }
            detail.text = "Bring orders to Marge at the post office to send them off.";
        }

        void Update()
        {
            if (TitleScreen.Showing || CatchReveal.Showing || DialogueRunner.Active || ServeUI.Showing || PauseMenu.Showing || MapUI.Showing) return;
            if (ShopCounter.I != null && ShopCounter.I.Open) return;
            if (GameInput.Journal.WasPressedThisFrame() || (Showing && GameInput.Back.WasPressedThisFrame())) Toggle();
            if (!Showing) return;
            if (Keyboard()) return;
        }

        bool Keyboard()
        {
            var kb = UnityEngine.InputSystem.Keyboard.current;
            var pad = UnityEngine.InputSystem.Gamepad.current;
            int d = 0;
            if ((kb != null && kb.qKey.wasPressedThisFrame) || (pad != null && pad.leftShoulder.wasPressedThisFrame)) d = -1;
            if ((kb != null && kb.eKey.wasPressedThisFrame) || (pad != null && pad.rightShoulder.wasPressedThisFrame)) d = 1;
            if (d != 0) Show((tab + d + TabNames.Length) % TabNames.Length);
            return d != 0;
        }
    }
}
