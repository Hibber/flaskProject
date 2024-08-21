import unittest
from unittest.mock import patch, MagicMock
from app import send_sms_reminder

class TestSendSMSReminder(unittest.TestCase):

    @patch('app.client.messages.create')
    def test_send_sms_reminder(self, mock_send_sms):
        # Arrange
        to = '+13605597650'
        body = 'This is a test message.'
        mock_response = MagicMock()
        mock_response.sid = 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
        mock_send_sms.return_value = mock_response

        # Act
        send_sms_reminder(to, body)

        # Assert
        mock_send_sms.assert_called_once_with(
            to=to,
            from_='+18333420817',  # This should match the Twilio number used in your function
            body=body
        )

        # Additional assertions can be added if needed
        self.assertEqual(mock_response.sid, 'SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')

if __name__ == '__main__':
    unittest.main()