using System;
using System.Configuration;
using System.Windows;
// using Resto.Front.Api; // Ensure correct namespace/version after adding SDK reference

namespace BonusPaymentPlugin
{
    // IMPORTANT: Ensure your class is public, has parameterless ctor, and inherits MarshalByRefObject.
    public sealed class Plugin : MarshalByRefObject /*, IFrontPlugin*/
    {
        private string apiBaseUrl;
        private string apiKey;
        private string paymentTypeName;

        public Plugin()
        {
        }

        // TODO: Uncomment and match the exact signature for your SDK version
        // public void Init(IInitParams initParams)
        public void Init()
        {
            try
            {
                apiBaseUrl = ConfigurationManager.AppSettings["ApiBaseUrl"] ?? string.Empty;
                apiKey = ConfigurationManager.AppSettings["ApiKey"] ?? string.Empty;
                paymentTypeName = ConfigurationManager.AppSettings["PaymentTypeName"] ?? "Бонусы";

                if (string.IsNullOrWhiteSpace(apiBaseUrl))
                    throw new InvalidOperationException("ApiBaseUrl is not configured");

                // TODO: Register payment processor factory for external payment type "paymentTypeName"
                // Example (pseudo):
                // var ops = PluginContext.Operations;
                // var ui = PluginContext.UI;
                // var log = PluginContext.Log;
                // var paymentType = ops.GetPaymentTypes().OfType<IExternalPaymentType>().First(t => t.Name == paymentTypeName);
                // var factory = new Payment.BonusPaymentProcessorFactory(apiBaseUrl, apiKey, ui, log, paymentType);
                // ops.RegisterPaymentSystem(factory);
            }
            catch (Exception ex)
            {
                // Attempt to show an error dialog in front UI if possible; otherwise swallow
                try { MessageBox.Show($"BonusPaymentPlugin init error: {ex.Message}"); } catch { }
                throw;
            }
        }

        public void Dispose()
        {
            // TODO: Unsubscribe if you subscribed to notifications
        }
    }
}
