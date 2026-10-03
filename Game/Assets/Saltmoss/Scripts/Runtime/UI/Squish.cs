using UnityEngine;
using UnityEngine.EventSystems;

namespace Saltmoss
{
    /// <summary>Selected/pressed buttons squash a little like soft clay, on stop-motion steps.</summary>
    public class Squish : MonoBehaviour, ISelectHandler, IDeselectHandler, IPointerEnterHandler, IPointerExitHandler, ISubmitHandler, IPointerDownHandler
    {
        float target = 1f, cur = 1f, kick;
        public void OnSelect(BaseEventData e) { target = 1.06f; AudioDirector.UI("ui_hover", 0.4f); }
        public void OnDeselect(BaseEventData e) => target = 1f;
        public void OnPointerEnter(PointerEventData e) { if (EventSystem.current != null) EventSystem.current.SetSelectedGameObject(gameObject); }
        public void OnPointerExit(PointerEventData e) { }
        public void OnSubmit(BaseEventData e) => kick = 1f;
        public void OnPointerDown(PointerEventData e) => kick = 1f;

        void Update()
        {
            if (!ClayClock.SteppedThisFrame && ClayClock.Fps > 0 && Time.timeScale > 0f) return;
            cur = Mathf.Lerp(cur, target, 0.6f);
            kick = Mathf.MoveTowards(kick, 0f, 0.34f);
            float sx = cur * (1f + kick * 0.08f), sy = cur * (1f - kick * 0.1f);
            transform.localScale = new Vector3(sx, sy, 1f);
        }
    }
}
