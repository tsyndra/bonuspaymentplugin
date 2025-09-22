using System;
using System.Windows;
using BonusPaymentPlugin.Loyalty;

namespace BonusPaymentPlugin.UI
{
    public partial class RedeemDialog : Window
    {
        private readonly LoyaltyClient loyaltyClient;

        public string CustomerIdOrPhone { get; private set; } = string.Empty;
        public decimal Available { get; private set; }
        public decimal RedeemAmount { get; private set; }

        public RedeemDialog() : this(null)
        {
        }

        public RedeemDialog(LoyaltyClient client)
        {
            InitializeComponent();
            loyaltyClient = client;
        }

        private async void OnCheck(object sender, RoutedEventArgs e)
        {
            try
            {
                CustomerIdOrPhone = CustomerInput.Text?.Trim() ?? string.Empty;
                if (string.IsNullOrWhiteSpace(CustomerIdOrPhone))
                {
                    MessageBox.Show("Введите телефон/карту");
                    return;
                }

                if (loyaltyClient == null)
                {
                    MessageBox.Show("Лояльность не инициализирована");
                    return;
                }

                var balance = await loyaltyClient.GetBalanceAsync(CustomerIdOrPhone);
                Available = balance.Balance;
                BalanceText.Text = Available.ToString("0.##");
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Ошибка: {ex.Message}");
            }
        }

        private void OnOk(object sender, RoutedEventArgs e)
        {
            try
            {
                if (!decimal.TryParse(RedeemAmountInput.Text, out var amount) || amount <= 0m)
                {
                    MessageBox.Show("Неверная сумма");
                    return;
                }
                if (amount > Available)
                {
                    MessageBox.Show("Сумма превышает доступный баланс");
                    return;
                }
                RedeemAmount = amount;
                DialogResult = true;
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Ошибка: {ex.Message}");
            }
        }
    }
}
