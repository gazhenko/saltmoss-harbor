using TMPro;
using UnityEngine;

namespace Saltmoss
{
    /// <summary>Walter's chalk board outside the harbour office: today's and tomorrow's weather, rewritten each morning.</summary>
    public class ForecastBoard : MonoBehaviour
    {
        public TextMeshPro text;
        int shownDay = -1, shownWeather = -1;

        void Update()
        {
            var D = GameState.D;
            if (text == null || (shownDay == D.day && shownWeather == D.weather)) return;
            shownDay = D.day;
            shownWeather = D.weather;
            text.text = $"<size=130%>FORECAST</size>\nToday: {GameFlow.WeatherName(D.weather)}\nTomorrow: {GameFlow.WeatherName(D.forecast)}";
        }
    }
}
