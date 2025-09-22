using System;
using System.Threading.Tasks;
using BonusPaymentPlugin.Loyalty;
using BonusPaymentPlugin.UI;

namespace BonusPaymentPlugin.Payment
{
    // TODO: Implement IExternalPaymentProcessor from Resto.Front.Api
    public sealed class BonusPaymentProcessor /* : IExternalPaymentProcessor */
    {
        private readonly LoyaltyClient loyaltyClient;
        private readonly string paymentSystemName;

        public BonusPaymentProcessor(/*IPaymentProcessorContext context,*/ LoyaltyClient loyaltyClient, string paymentSystemName)
        {
            this.loyaltyClient = loyaltyClient ?? throw new ArgumentNullException(nameof(loyaltyClient));
            this.paymentSystemName = paymentSystemName ?? throw new ArgumentNullException(nameof(paymentSystemName));
        }

        // Example main entry (adjust to SDK):
        // public PaymentOperationResult ProcessPayment(decimal sum, IOrder order)
        // {
        //     var dialog = new RedeemDialog();
        //     if (dialog.ShowDialog() != true)
        //         return PaymentOperationResult.Canceled;
        //
        //     var request = new ReserveRequest
        //     {
        //         OrderId = order.Id.ToString(),
        //         CustomerId = dialog.CustomerId,
        //         Amount = dialog.RedeemAmount
        //     };
        //
        //     var reserve = loyaltyClient.ReserveAsync(request).GetAwaiter().GetResult();
        //     // Save reserve.ReservationId in payment comment/metadata
        //     return PaymentOperationResult.Success(dialog.RedeemAmount, reserve.ReservationId);
        // }
    }
}
