using System;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>Code-built uGUI in clay: slab panels, chunky text, squishy buttons. Reference resolution 1920x1080.</summary>
    public static class ClayUI
    {
        public static readonly Color Ink = new Color32(0x3a, 0x2a, 0x22, 0xff);
        public static readonly Color Cream = new Color32(0xf6, 0xee, 0xdb, 0xff);
        public static readonly Color Red = new Color32(0xc2, 0x4a, 0x3a, 0xff);
        public static readonly Color Gold = new Color32(0xf2, 0xb8, 0x4b, 0xff);
        public static readonly Color Teal = new Color32(0x3f, 0x7f, 0x7c, 0xff);
        public static readonly Color Muted = new Color32(0x7a, 0x68, 0x58, 0xff);

        public static Canvas Canvas(string name, int order, Transform parent = null)
        {
            var go = new GameObject(name, typeof(RectTransform));
            if (parent != null) go.transform.SetParent(parent, false);
            var c = go.AddComponent<Canvas>();
            c.renderMode = RenderMode.ScreenSpaceOverlay;
            c.sortingOrder = order;
            var s = go.AddComponent<CanvasScaler>();
            s.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            s.referenceResolution = new Vector2(1920, 1080);
            s.matchWidthOrHeight = 0.5f;
            go.AddComponent<GraphicRaycaster>();
            GameInput.EnsureEventSystem();
            return c;
        }

        public static RectTransform Rect(string name, Transform parent, Vector2 anchorMin, Vector2 anchorMax, Vector2 pos, Vector2 size, Vector2? pivot = null)
        {
            var go = new GameObject(name, typeof(RectTransform));
            var rt = (RectTransform)go.transform;
            rt.SetParent(parent, false);
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.pivot = pivot ?? new Vector2(0.5f, 0.5f);
            rt.anchoredPosition = pos;
            rt.sizeDelta = size;
            return rt;
        }

        public static RectTransform Fill(string name, Transform parent, float inset = 0f)
        {
            var rt = Rect(name, parent, Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            rt.offsetMin = new Vector2(inset, inset);
            rt.offsetMax = new Vector2(-inset, -inset);
            return rt;
        }

        public static Image Panel(string name, Transform parent, string sprite, Vector2 anchor, Vector2 pos, Vector2 size, Color? tint = null, Vector2? pivot = null)
        {
            var rt = Rect(name, parent, anchor, anchor, pos, size, pivot);
            var img = rt.gameObject.AddComponent<Image>();
            img.sprite = UIBank.I.Get(sprite);
            img.type = img.sprite != null && img.sprite.border.sqrMagnitude > 0 ? Image.Type.Sliced : Image.Type.Simple;
            img.color = tint ?? Color.white;
            img.raycastTarget = false;
            if (img.sprite == null) img.color = tint ?? new Color(0.94f, 0.89f, 0.78f, 0.95f);
            return img;
        }

        public static TextMeshProUGUI Text(string name, Transform parent, string text, float size, Color color, TextAlignmentOptions align = TextAlignmentOptions.Left, bool display = false)
        {
            var rt = Fill(name, parent);
            var t = rt.gameObject.AddComponent<TextMeshProUGUI>();
            var font = display ? UIBank.I.display : UIBank.I.body;
            if (font != null) t.font = font;
            t.text = text;
            t.fontSize = size;
            t.color = color;
            t.alignment = align;
            t.raycastTarget = false;
            t.textWrappingMode = TextWrappingModes.Normal;
            t.richText = true;
            return t;
        }

        public static Button Button(string name, Transform parent, string label, Vector2 anchor, Vector2 pos, Vector2 size, Action onClick, float fontSize = 34f)
        {
            var img = Panel(name, parent, "button", anchor, pos, size);
            img.raycastTarget = true;
            var b = img.gameObject.AddComponent<UnityEngine.UI.Button>();
            b.transition = Selectable.Transition.SpriteSwap;
            var st = new SpriteState { highlightedSprite = UIBank.I.Get("button_on"), selectedSprite = UIBank.I.Get("button_on"), pressedSprite = UIBank.I.Get("button_on") };
            b.spriteState = st;
            var t = Text("Label", img.transform, label, fontSize, Ink, TextAlignmentOptions.Center, true);
            t.margin = new Vector4(16, 6, 16, 10);
            b.onClick.AddListener(() => { AudioDirector.UI("ui_click"); onClick?.Invoke(); });
            img.gameObject.AddComponent<Squish>();
            return b;
        }

        public static void Select(Selectable s)
        {
            if (s == null) return;
            var es = EventSystem.current;
            if (es != null) es.SetSelectedGameObject(s.gameObject);
        }

        /// <summary>A key cap / controller button chip showing the bound control, e.g. [E] Talk.</summary>
        public static TextMeshProUGUI Prompt(Transform parent, Vector2 anchor, Vector2 pos, out Image cap)
        {
            cap = Panel("Cap", parent, "keycap", anchor, pos, new Vector2(64, 64));
            var k = Text("Key", cap.transform, "E", 30, Ink, TextAlignmentOptions.Center, true);
            k.margin = new Vector4(6, 0, 6, 6);
            k.textWrappingMode = TextWrappingModes.NoWrap;
            k.enableAutoSizing = true;
            k.fontSizeMin = 16;
            k.fontSizeMax = 30;
            return k;
        }
    }
}
