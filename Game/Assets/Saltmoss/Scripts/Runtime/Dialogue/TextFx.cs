using TMPro;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>
    /// Wavy and shaky text for &lt;link="w"&gt; / &lt;link="s"&gt; ranges, plus a little pop as each letter appears.
    /// Like everything else in the set it moves on twos: vertices are only re-posed on stop-motion steps.
    /// </summary>
    [RequireComponent(typeof(TMP_Text))]
    public class TextFx : MonoBehaviour
    {
        TMP_Text text;
        int lastVisible = -1;
        readonly float[] pop = new float[1024];

        void Awake() => text = GetComponent<TMP_Text>();

        public void ResetPops()
        {
            System.Array.Clear(pop, 0, pop.Length);
            lastVisible = -1;
        }

        void LateUpdate()
        {
            if (text == null || !text.gameObject.activeInHierarchy) return;
            bool step = ClayClock.SteppedThisFrame || ClayClock.Fps == 0 || Time.timeScale == 0f;
            int vis = Mathf.Min(text.maxVisibleCharacters, text.textInfo.characterCount);
            if (vis != lastVisible)
            {
                for (int i = Mathf.Max(0, lastVisible); i < vis && i < pop.Length; i++) pop[i] = 1f;
                lastVisible = vis;
                step = true;
            }
            if (!step) return;
            text.ForceMeshUpdate();
            var info = text.textInfo;
            float t = ClayClock.Fps > 0 ? ClayClock.Frame / (float)ClayClock.Fps : Time.unscaledTime;
            bool any = false;
            for (int c = 0; c < info.characterCount && c < pop.Length; c++)
            {
                var ch = info.characterInfo[c];
                if (!ch.isVisible) continue;
                int link = LinkOf(info, c);
                float p = pop[c];
                if (link < 0 && p <= 0f) continue;
                any = true;
                var verts = info.meshInfo[ch.materialReferenceIndex].vertices;
                int vi = ch.vertexIndex;
                Vector3 mid = (verts[vi] + verts[vi + 2]) * 0.5f;
                Vector3 off = Vector3.zero;
                float sc = 1f + p * 0.35f;
                if (link == 0) off.y = Mathf.Sin(t * 7f + c * 0.55f) * ch.pointSize * 0.12f;
                else if (link == 1) off = new Vector3(Hash(c, 1) - 0.5f, Hash(c, 2) - 0.5f, 0f) * ch.pointSize * 0.12f;
                for (int k = 0; k < 4; k++) verts[vi + k] = mid + (verts[vi + k] - mid) * sc + off;
                pop[c] = Mathf.Max(0f, p - 0.5f);
            }
            if (any) text.UpdateVertexData(TMP_VertexDataUpdateFlags.Vertices);
        }

        static float Hash(int c, int k) => Mathf.Repeat(Mathf.Sin((c * 12.9898f + k * 78.233f + ClayClock.Frame * 3.17f)) * 43758.5453f, 1f);

        static int LinkOf(TMP_TextInfo info, int c)
        {
            for (int l = 0; l < info.linkCount; l++)
            {
                var li = info.linkInfo[l];
                if (c >= li.linkTextfirstCharacterIndex && c < li.linkTextfirstCharacterIndex + li.linkTextLength)
                    return li.GetLinkID() == "w" ? 0 : li.GetLinkID() == "s" ? 1 : -1;
            }
            return -1;
        }
    }
}
