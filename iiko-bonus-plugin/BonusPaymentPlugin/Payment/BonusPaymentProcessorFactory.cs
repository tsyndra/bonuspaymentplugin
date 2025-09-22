using System;
using BonusPaymentPlugin.Loyalty;

namespace BonusPaymentPlugin.Payment
{
    // TODO: Implement IExternalPaymentProcessorFactory from Resto.Front.Api and expose PaymentSystemName/Id
    public sealed class BonusPaymentProcessorFactory /* : IExternalPaymentProcessorFactory */
    {
        private readonly LoyaltyClient loyaltyClient;
        private readonly string paymentSystemName;

        public BonusPaymentProcessorFactory(string apiBaseUrl, string apiKey, string paymentSystemName)
        {
            if (string.IsNullOrWhiteSpace(apiBaseUrl))
                throw new ArgumentException("apiBaseUrl is required", nameof(apiBaseUrl));
            if (string.IsNullOrWhiteSpace(paymentSystemName))
                throw new ArgumentException("paymentSystemName is required", nameof(paymentSystemName));

            this.loyaltyClient = new LoyaltyClient(apiBaseUrl, apiKey);
            this.paymentSystemName = paymentSystemName;
        }

        // Example signatures (adjust to SDK):
        // public string PaymentSystemName => paymentSystemName;
        // public Guid PaymentSystemId => new Guid("11111111-2222-3333-4444-555555555555");
        // public IExternalPaymentProcessor CreatePaymentProcessor(IPaymentProcessorContext context)
        //     => new BonusPaymentProcessor(context, loyaltyClient, paymentSystemName);
    }
}
