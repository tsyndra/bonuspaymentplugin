using System;
using System.Configuration;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;

namespace BonusPaymentPlugin.Loyalty
{
    public sealed class LoyaltyClient : IDisposable
    {
        private readonly HttpClient http;
        private readonly string baseUrl;

        public LoyaltyClient(string apiBaseUrl, string apiKey)
        {
            baseUrl = apiBaseUrl.TrimEnd('/');
            http = new HttpClient();
            if (!string.IsNullOrWhiteSpace(apiKey))
                http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
            http.Timeout = TimeSpan.FromSeconds(10);
        }

        public async Task<BalanceResponse> GetBalanceAsync(string customerIdOrPhone)
        {
            var url = $"{baseUrl}/loyalty/balance?customerId={Uri.EscapeDataString(customerIdOrPhone)}";
            var resp = await http.GetAsync(url).ConfigureAwait(false);
            resp.EnsureSuccessStatusCode();
            var json = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
            return JsonConvert.DeserializeObject<BalanceResponse>(json);
        }

        public async Task<ReserveResponse> ReserveAsync(ReserveRequest request)
        {
            var url = $"{baseUrl}/loyalty/reserve";
            var json = JsonConvert.SerializeObject(request);
            var resp = await http.PostAsync(url, new StringContent(json, Encoding.UTF8, "application/json")).ConfigureAwait(false);
            resp.EnsureSuccessStatusCode();
            var body = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
            return JsonConvert.DeserializeObject<ReserveResponse>(body);
        }

        public async Task CommitAsync(CommitRequest request)
        {
            var url = $"{baseUrl}/loyalty/commit";
            var json = JsonConvert.SerializeObject(request);
            var resp = await http.PostAsync(url, new StringContent(json, Encoding.UTF8, "application/json")).ConfigureAwait(false);
            resp.EnsureSuccessStatusCode();
        }

        public async Task CancelAsync(CancelRequest request)
        {
            var url = $"{baseUrl}/loyalty/cancel";
            var json = JsonConvert.SerializeObject(request);
            var resp = await http.PostAsync(url, new StringContent(json, Encoding.UTF8, "application/json")).ConfigureAwait(false);
            resp.EnsureSuccessStatusCode();
        }

        public void Dispose()
        {
            http?.Dispose();
        }
    }
}
