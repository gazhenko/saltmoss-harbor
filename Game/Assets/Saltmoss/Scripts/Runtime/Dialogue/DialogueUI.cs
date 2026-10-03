using System;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Saltmoss
{
    /// <summary>
    /// The dialogue box: a cream clay slab along the bottom, the speaker's live portrait in a clay frame at its left,
    /// a coloured name tag, typewriter text with wavy/shaky effects, a bobbing "next" arrow and clay choice buttons.
    /// </summary>
    public class DialogueUI : MonoBehaviour
    {
        public static DialogueUI I { get; private set; }

        Canvas canvas;
        RectTransform box, portraitFrame, choicesRoot, arrowRt;
        RawImage portrait;
        Image nameTag;
        TextMeshProUGUI nameText, body;
        TextFx fx;
        CanvasGroup group;
        readonly List<Button> choiceButtons = new List<Button>();
        float showT;
        bool shown;
        Vector2 boxRest;

        public TextMeshProUGUI Body => body;
        /// <summary>Modal panels opened from dialogue (shops, museum) tuck the box away while they're up.</summary>
        public static bool Suspended;

        public static DialogueUI Ensure()
        {
            if (I != null) return I;
            var go = new GameObject("DialogueUI");
            DontDestroyOnLoad(go);
            I = go.AddComponent<DialogueUI>();
            I.Build();
            return I;
        }

        void Build()
        {
            canvas = ClayUI.Canvas("DialogueCanvas", 50, transform);
            group = canvas.gameObject.AddComponent<CanvasGroup>();
            group.alpha = 0f;
            group.blocksRaycasts = false;
            var root = canvas.transform;

            var boxImg = ClayUI.Panel("Box", root, "panel_cream", new Vector2(0.5f, 0f), new Vector2(40f, 28f), new Vector2(1440f, 290f), null, new Vector2(0.5f, 0f));
            box = boxImg.rectTransform;
            boxRest = box.anchoredPosition;
            body = ClayUI.Text("Body", box, "", 40f, ClayUI.Ink, TextAlignmentOptions.TopLeft);
            body.rectTransform.offsetMin = new Vector2(250f, 46f);
            body.rectTransform.offsetMax = new Vector2(-70f, -56f);
            body.lineSpacing = 6f;
            fx = body.gameObject.AddComponent<TextFx>();

            // portrait in a sand-clay frame, overlapping the box's left edge
            var frame = ClayUI.Panel("PortraitFrame", root, "panel_sand", new Vector2(0.5f, 0f), new Vector2(-610f, 120f), new Vector2(330f, 330f), null, new Vector2(0.5f, 0f));
            portraitFrame = frame.rectTransform;
            var maskImg = ClayUI.Panel("Mask", portraitFrame, "panel_paper", new Vector2(0.5f, 0.5f), new Vector2(-2f, 4f), new Vector2(268f, 268f));
            var mask = maskImg.gameObject.AddComponent<Mask>();
            mask.showMaskGraphic = true;
            var prt = ClayUI.Fill("Portrait", maskImg.transform, 14f);
            portrait = prt.gameObject.AddComponent<RawImage>();
            portrait.raycastTarget = false;

            // name tag (coloured slab)
            nameTag = ClayUI.Panel("NameTag", root, "tag", new Vector2(0.5f, 0f), new Vector2(-300f, 290f), new Vector2(360f, 96f), Color.white, new Vector2(0.5f, 0f));
            nameText = ClayUI.Text("Name", nameTag.transform, "", 40f, ClayUI.Cream, TextAlignmentOptions.Center, true);
            nameText.margin = new Vector4(18, 4, 18, 14);

            var arrow = ClayUI.Panel("Next", box, "arrow", new Vector2(1f, 0f), new Vector2(-70f, 52f), new Vector2(60f, 60f));
            arrowRt = arrow.rectTransform;

            choicesRoot = ClayUI.Rect("Choices", root, new Vector2(1f, 0f), new Vector2(1f, 0f), new Vector2(-150f, 330f), new Vector2(560f, 420f), new Vector2(1f, 0f));
        }

        public void Show(bool on)
        {
            if (on && !shown) showT = 0f;
            shown = on;
            group.blocksRaycasts = on;
            if (!on) { HideChoices(); PortraitStage.I?.Hide(); }
        }

        public void SetSpeaker(string id)
        {
            bool narr = string.IsNullOrEmpty(id) || id == "narrator";
            portraitFrame.gameObject.SetActive(!narr);
            nameTag.gameObject.SetActive(!narr);
            body.rectTransform.offsetMin = new Vector2(narr ? 70f : 250f, 46f);
            if (narr) { PortraitStage.I?.Hide(); return; }
            var m = Cast.Get(id);
            nameText.text = m.name;
            nameTag.color = m.tag;
            var stage = PortraitStage.Ensure();
            stage.Show(id);
            portrait.texture = stage.Texture;
        }

        public void SetText(string rich)
        {
            body.text = rich;
            body.maxVisibleCharacters = 0;
            body.ForceMeshUpdate();
            fx.ResetPops();
        }

        public int Total => body.textInfo.characterCount;
        public int Visible { get => body.maxVisibleCharacters; set => body.maxVisibleCharacters = value; }
        public char CharAt(int i) => i >= 0 && i < body.textInfo.characterCount ? body.textInfo.characterInfo[i].character : ' ';
        public void ShowArrow(bool on) => arrowRt.gameObject.SetActive(on);

        public void ShowChoices(List<string> labels, Action<int> chosen)
        {
            HideChoices();
            for (int i = 0; i < labels.Count; i++)
            {
                int k = i;
                var b = ClayUI.Button("Choice" + i, choicesRoot, labels[i], new Vector2(1f, 0f), new Vector2(0f, (labels.Count - 1 - i) * 100f), new Vector2(560f, 88f),
                    () => chosen(k), 32f);
                ((RectTransform)b.transform).pivot = new Vector2(1f, 0f);
                b.GetComponentInChildren<TextMeshProUGUI>().font = UIBank.I.body;
                choiceButtons.Add(b);
            }
            for (int i = 0; i < choiceButtons.Count; i++)
            {
                var nav = new Navigation { mode = Navigation.Mode.Explicit };
                nav.selectOnUp = choiceButtons[(i + choiceButtons.Count - 1) % choiceButtons.Count];
                nav.selectOnDown = choiceButtons[(i + 1) % choiceButtons.Count];
                choiceButtons[i].navigation = nav;
            }
            if (choiceButtons.Count > 0) ClayUI.Select(choiceButtons[0]);
        }

        public void HideChoices()
        {
            foreach (var b in choiceButtons) if (b != null) Destroy(b.gameObject);
            choiceButtons.Clear();
        }

        void Update()
        {
            // slide/fade in, and the arrow bobs on twos
            showT += Time.unscaledDeltaTime;
            float target = shown && !Suspended ? 1f : 0f;
            group.alpha = Mathf.MoveTowards(group.alpha, target, Time.unscaledDeltaTime * 6f);
            float e = 1f - Mathf.Pow(1f - Mathf.Clamp01(showT * 4f), 3f);
            box.anchoredPosition = boxRest + Vector2.down * (shown ? (1f - e) * 60f : 0f);
            if (ClayClock.SteppedThisFrame || Time.timeScale == 0f)
                arrowRt.anchoredPosition = new Vector2(-70f, 52f + Mathf.Abs(Mathf.Sin(Time.unscaledTime * 4f)) * 10f);
        }
    }
}
