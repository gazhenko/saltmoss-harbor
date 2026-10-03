using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>Pause, settings (sound, stop-motion, camera, text, display) and controls remapping, all in clay.</summary>
    public class PauseMenu : MonoBehaviour
    {
        public static bool Showing { get; private set; }
        static PauseMenu inst;
        Canvas canvas;
        RectTransform body;
        TextMeshProUGUI title;
        readonly List<GameObject> items = new List<GameObject>();
        enum Page { Main, Settings, Controls }
        Page page;
        bool fromTitle;
        Action onClose;
        float openedAt;

        public static PauseMenu Ensure()
        {
            if (inst != null) return inst;
            var go = new GameObject("PauseMenu");
            DontDestroyOnLoad(go);
            inst = go.AddComponent<PauseMenu>();
            inst.Build();
            return inst;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot() => Ensure();

        void Build()
        {
            canvas = ClayUI.Canvas("PauseCanvas", 80, transform);
            var dim = ClayUI.Fill("Dim", canvas.transform);
            dim.gameObject.AddComponent<Image>().color = new Color(0.08f, 0.06f, 0.05f, 0.55f);
            var panel = ClayUI.Panel("Panel", canvas.transform, "panel_cream", new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(1180f, 900f));
            title = ClayUI.Text("Title", panel.transform, "Paused", 54f, ClayUI.Red, TextAlignmentOptions.Top, true);
            title.margin = new Vector4(0, 30, 0, 0);
            body = ClayUI.Rect("Body", panel.transform, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), new Vector2(0f, -120f), new Vector2(1060f, 740f), new Vector2(0.5f, 1f));
            var vl = body.gameObject.AddComponent<VerticalLayoutGroup>();
            vl.spacing = 12f;
            vl.childAlignment = TextAnchor.UpperCenter;
            vl.childControlHeight = false;
            vl.childControlWidth = false;
            vl.childForceExpandHeight = false;
            vl.childForceExpandWidth = false;
            canvas.gameObject.SetActive(false);
        }

        public static void OpenSettings(Action closed)
        {
            var m = Ensure();
            m.fromTitle = true;
            m.onClose = closed;
            m.Open(Page.Settings);
        }

        void Open(Page p)
        {
            Showing = true;
            openedAt = Time.unscaledTime;
            canvas.gameObject.SetActive(true);
            if (!fromTitle) { Time.timeScale = 0f; AudioListener.pause = false; }
            AudioDirector.UI("ui_open");
            Show(p);
        }

        void Close()
        {
            Showing = false;
            canvas.gameObject.SetActive(false);
            Time.timeScale = 1f;
            Settings.Save();
            AudioDirector.UI("ui_close");
            var cb = onClose;
            onClose = null;
            fromTitle = false;
            cb?.Invoke();
        }

        void Clear()
        {
            foreach (var g in items) Destroy(g);
            items.Clear();
        }

        Button Btn(string label, Action a, float w = 560f)
        {
            var b = ClayUI.Button(label, body, label, new Vector2(0.5f, 1f), Vector2.zero, new Vector2(w, 80f), a, 32f);
            items.Add(b.gameObject);
            return b;
        }

        void Show(Page p)
        {
            page = p;
            Clear();
            Selectable first = null;
            switch (p)
            {
                case Page.Main:
                    title.text = "Paused";
                    first = Btn("Back to the harbour", Close);
                    Btn("Settings", () => Show(Page.Settings));
                    Btn("Controls", () => Show(Page.Controls));
                    Btn("Save game", () => { GameState.Save(); GameState.Say("Saved!"); Close(); });
                    Btn("Save & quit", () => { GameState.Save(); Application.Quit(); });
                    break;
                case Page.Settings:
                    title.text = "Settings";
                    first = Slider("Music", Settings.Music, v => Settings.Music = v);
                    Slider("Sounds", Settings.Sfx, v => Settings.Sfx = v);
                    Slider("Voices", Settings.Voice, v => { Settings.Voice = v; VoiceBlips.I?.Speak("pip", 'o', 0f, 0f, true); });
                    Slider("Ambience", Settings.Ambience, v => Settings.Ambience = v);
                    Choice("Stop-motion", new[] { "On twos (12 fps)", "On ones (24 fps)", "Off (smooth)" }, Settings.Motion == StopMotion.Twos ? 0 : Settings.Motion == StopMotion.Ones ? 1 : 2,
                        i => { Settings.Motion = i == 0 ? StopMotion.Twos : i == 1 ? StopMotion.Ones : StopMotion.Off; Settings.Apply(); });
                    Choice("Full-film camera", new[] { "Off", "On" }, Settings.FilmCamera ? 1 : 0, i => { Settings.FilmCamera = i == 1; Settings.Apply(); });
                    Choice("Depth of field", new[] { "On", "Off" }, Settings.DepthOfField ? 0 : 1, i => { Settings.DepthOfField = i == 0; Settings.Apply(); });
                    Choice("Text speed", new[] { "Slow", "Normal", "Fast" }, Settings.TextSpeed < 0.9f ? 0 : Settings.TextSpeed > 1.3f ? 2 : 1, i => Settings.TextSpeed = i == 0 ? 0.65f : i == 1 ? 1f : 1.7f);
                    Slider("Camera speed", Mathf.InverseLerp(0.3f, 3f, Settings.LookSensitivity), v => Settings.LookSensitivity = Mathf.Lerp(0.3f, 3f, v));
                    Choice("Quality", new[] { "Low", "Medium", "High" }, Settings.Quality, i => { Settings.Quality = i; Settings.Apply(); });
                    Choice("Display", new[] { "Fullscreen", "Windowed" }, Settings.Fullscreen ? 0 : 1, i => { Settings.Fullscreen = i == 0; Settings.Apply(); });
                    Btn("Done", () => { Settings.Apply(); if (fromTitle) Close(); else Show(Page.Main); }, 360f);
                    break;
                case Page.Controls:
                    title.text = "Controls";
                    first = ControlsRows();
                    Btn("Reset to defaults", () => { GameInput.ResetAllBindings(); Show(Page.Controls); }, 460f);
                    Btn("Done", () => Show(Page.Main), 360f);
                    break;
            }
            Nav();
            ClayUI.Select(first);
        }

        void Nav()
        {
            var sel = new List<Selectable>();
            foreach (var g in items) foreach (var s in g.GetComponentsInChildren<Selectable>()) sel.Add(s);
            foreach (var s in sel) { var n = s.navigation; n.mode = Navigation.Mode.Automatic; s.navigation = n; }
        }

        RectTransform Row(string label, float h = 66f)
        {
            var row = ClayUI.Rect(label, body, new Vector2(0.5f, 1f), new Vector2(0.5f, 1f), Vector2.zero, new Vector2(1000f, h));
            var t = ClayUI.Text("Label", row, label, 30f, ClayUI.Ink, TextAlignmentOptions.Left, true);
            t.margin = new Vector4(10, 0, 0, 6);
            items.Add(row.gameObject);
            return row;
        }

        Selectable Slider(string label, float value, Action<float> set)
        {
            var row = Row(label);
            var back = ClayUI.Panel("Back", row, "bar_back", new Vector2(1f, 0.5f), new Vector2(-260f, 0f), new Vector2(480f, 40f));
            var s = back.gameObject.AddComponent<UnityEngine.UI.Slider>();
            var fillArea = ClayUI.Fill("FillArea", back.transform, 6f);
            var fill = ClayUI.Panel("Fill", fillArea, "bar_fill", new Vector2(0f, 0.5f), Vector2.zero, new Vector2(0f, 0f));
            fill.rectTransform.anchorMin = Vector2.zero;
            fill.rectTransform.anchorMax = new Vector2(0f, 1f);
            fill.rectTransform.sizeDelta = Vector2.zero;
            var handleArea = ClayUI.Fill("HandleArea", back.transform, 0f);
            var handle = ClayUI.Panel("Handle", handleArea, "dot", new Vector2(0f, 0.5f), Vector2.zero, new Vector2(56f, 56f));
            handle.raycastTarget = true;
            back.raycastTarget = true;
            s.fillRect = fill.rectTransform;
            s.handleRect = handle.rectTransform;
            s.targetGraphic = handle;
            s.minValue = 0f;
            s.maxValue = 1f;
            s.value = value;
            s.onValueChanged.AddListener(v => set(v));
            back.gameObject.AddComponent<Squish>();
            return s;
        }

        Selectable Choice(string label, string[] options, int current, Action<int> set)
        {
            var row = Row(label);
            int idx = current;
            TextMeshProUGUI txt = null;
            var b = ClayUI.Button("Choice", row, options[idx], new Vector2(1f, 0.5f), new Vector2(-260f, 0f), new Vector2(480f, 62f), () =>
            {
                idx = (idx + 1) % options.Length;
                txt.text = options[idx];
                set(idx);
            }, 28f);
            txt = b.GetComponentInChildren<TextMeshProUGUI>();
            return b;
        }

        Button ControlsRows()
        {
            Button first = null;
            for (int i = 0; i < GameInput.BindNames.Length; i++)
            {
                var bind = (Bind)i;
                var row = Row(GameInput.BindNames[i], 54f);
                row.GetComponentInChildren<TextMeshProUGUI>().fontSize = 24f;
                for (int sIdx = 0; sIdx < 3; sIdx++)
                {
                    var slot = (Slot)sIdx;
                    TextMeshProUGUI txt = null;
                    var b = ClayUI.Button("Slot", row, GameInput.Label(bind, slot), new Vector2(1f, 0.5f), new Vector2(-470f + sIdx * 180f + 90f, 0f), new Vector2(170f, 52f), null, 22f);
                    txt = b.GetComponentInChildren<TextMeshProUGUI>();
                    b.onClick.AddListener(() =>
                    {
                        txt.text = "…";
                        var op = GameInput.StartRebind(bind, slot, ok => { txt.text = GameInput.Label(bind, slot); if (GameInput.LastConflict != null) GameState.Say($"Moved from {GameInput.LastConflict}"); });
                        if (op == null) txt.text = GameInput.Label(bind, slot);
                    });
                    if (first == null) first = b;
                }
            }
            return first;
        }

        void Update()
        {
            if (GameInput.Capturing) return;
            if (!Showing)
            {
                if (TitleScreen.Showing || JournalUI.Showing || ServeUI.Showing) return;
                if (GameInput.Pause.WasPressedThisFrame() && !DialogueRunner.Active && !CatchReveal.Showing) { fromTitle = false; Open(Page.Main); }
                return;
            }
            if (Time.unscaledTime - openedAt > 0.2f && (GameInput.Back.WasPressedThisFrame() || GameInput.Pause.WasPressedThisFrame()))
            {
                if (page == Page.Main || fromTitle) Close(); else Show(Page.Main);
            }
        }
    }
}
