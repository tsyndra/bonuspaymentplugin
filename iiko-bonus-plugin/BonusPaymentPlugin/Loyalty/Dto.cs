using System;

namespace BonusPaymentPlugin.Loyalty
{
    public sealed class BalanceResponse
    {
        public decimal Balance { get; set; }
        public decimal Pending { get; set; }
    }

    public sealed class ReserveRequest
    {
        public string OrderId { get; set; } = string.Empty;
        public string CustomerIdOrPhone { get; set; } = string.Empty;
        public decimal Amount { get; set; }
        public int TtlSeconds { get; set; } = 300;
    }

    public sealed class ReserveResponse
    {
        public string ReservationId { get; set; } = string.Empty;
        public decimal Reserved { get; set; }
    }

    public sealed class CommitRequest
    {
        public string ReservationId { get; set; } = string.Empty;
        public string ReceiptNumber { get; set; } = string.Empty;
        public DateTime? ReceiptDate { get; set; }
    }

    public sealed class CancelRequest
    {
        public string ReservationId { get; set; } = string.Empty;
        public string Reason { get; set; } = string.Empty;
    }
}
