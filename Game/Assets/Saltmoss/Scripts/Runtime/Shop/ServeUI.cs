using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>The serving tray: the customer's order on the left, the ice display's stock as a clay grid to pick from.</summary>
    public class ServeUI : MonoBehaviour
    {
        public static bool Showing { get; private set; }
        static ServeUI inst;

        Canvas canvas;
        RectTransform grid;
        Image orderIcon;
        TextMeshProUGUI orderText;
        readonly List<GameObject> cells = new List<GameObject>();
        Action<string> onPick;
        Button sorry;
        float openedAt;

        public static void Open(Customer c, Action<string> pick)
        {
            if (inst == null)
            {
                var go = new GameObject("ServeUI");
                DontDestroyOnLoad(go);
                inst = go.AddComponent<ServeUI>();
                inst.Build();
            }
            inst.Show(c, pick);
        }

        void Build()
        {
            canvas = ClayUI.Canvas("ServeCanvas", 45, transform);
            var root = canvas.transform;
            var panel = ClayUI.Panel("Panel", root, "panel_cream", new Vector2(0.5f, 0.5f), new Vector2(0f, -20f), new Vector2(1500f, 760f));
            var title = ClayUI.Text("Title", panel.transform, "The Salty Puffin", 54f, ClayUI.Red, TextAlignmentOptions.Top, true);
            title.margin = new Vector4(0, 34, 0, 0);
            var order = ClayUI.Panel("Order", panel.transform, "panel_paper", new Vector2(0f, 0.5f), new Vector2(60f, -10f), new Vector2(380f, 520f), null, new Vector2(0f, 0.5f));
            orderIcon = ClayUI.Panel("Icon", order.transform, null, new Vector2(0.5f, 0.62f), Vector2.zero, new Vector2(260f, 260f));
            orderIcon.color = Color.white;
            orderIcon.preserveAspect = true;
            orderText = ClayUI.Text("Text", order.transform, "", 34f, ClayUI.Ink, TextAlignmentOptions.Bottom, true);
            orderText.margin = new Vector4(20, 0, 20, 40);
            grid = ClayUI.Rect("Grid", panel.transform, new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(480f, 10f), new Vector2(960f, 520f), new Vector2(0f, 0.5f));
            var gl = grid.gameObject.AddComponent<GridLayoutGroup>();
            gl.cellSize = new Vector2(176f, 200f);
            gl.spacing = new Vector2(18f, 18f);
            gl.constraint = GridLayoutGroup.Constraint.FixedColumnCount;
            gl.constraintCount = 5;
            sorry = ClayUI.Button("Sorry", panel.transform, "Sorry, none today", new Vector2(0.5f, 0f), new Vector2(240f, 50f), new Vector2(420f, 86f), () => Pick(null), 30f);
            canvas.gameObject.SetActive(false);
        }

        void Show(Customer c, Action<string> pick)
        {
            onPick = pick;
            openedAt = Time.unscaledTime;
            Showing = true;
            canvas.gameObject.SetActive(true);
            if (GameFlow.I != null) GameFlow.I.InMenu = true;
            var want = Catalog.Get(c.Wants);
            orderIcon.sprite = ItemStage.Ensure().Icon(c.Wants);
            orderText.text = $"\"{want.name} ×{c.Count}, please!\"";
            foreach (var g in cells) Destroy(g);
            cells.Clear();
            Button first = null, match = null;
            var ids = new List<string>();
            foreach (var s in GameState.D.stock) if (!ids.Contains(s.id)) ids.Add(s.id);
            foreach (var id in ids)
            {
                var def = Catalog.Get(id);
                int n = GameState.Count(GameState.D.stock, id);
                var cell = ClayUI.Panel("Cell", grid, "slot", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(176f, 200f));
                cell.raycastTarget = true;
                var b = cell.gameObject.AddComponent<Button>();
                b.transition = Selectable.Transition.ColorTint;
                var cb = b.colors; cb.selectedColor = new Color(1f, 0.85f, 0.5f); cb.highlightedColor = cb.selectedColor; b.colors = cb;
                string pid = id;
                b.onClick.AddListener(() => { AudioDirector.UI("ui_click"); Pick(pid); });
                cell.gameObject.AddComponent<Squish>();
                var ic = ClayUI.Panel("Icon", cell.transform, null, new Vector2(0.5f, 0.6f), Vector2.zero, new Vector2(130f, 130f));
                ic.sprite = ItemStage.Ensure().Icon(id);
                ic.color = Color.white;
                ic.preserveAspect = true;
                var t = ClayUI.Text("Label", cell.transform, $"{def.name}\n<b>×{n}</b>", 22f, ClayUI.Ink, TextAlignmentOptions.Bottom);
                t.margin = new Vector4(8, 0, 8, 12);
                cells.Add(cell.gameObject);
                if (first == null) first = b;
                if (id == c.Wants) match = b;
            }
            ClayUI.Select(match != null ? match : first != null ? first : sorry);
            AudioDirector.UI("ui_open", 0.6f);
        }

        void Pick(string id)
        {
            if (Time.unscaledTime - openedAt < 0.25f) return;   // the key that opened the tray must not also pick
            canvas.gameObject.SetActive(false);
            Showing = false;
            if (GameFlow.I != null) GameFlow.I.InMenu = false;
            var cb = onPick;
            onPick = null;
            cb?.Invoke(id);
        }

        void Update()
        {
            if (Showing && GameInput.Back.WasPressedThisFrame()) Pick(null);
        }
    }
}
