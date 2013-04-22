from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import encoders
import smtplib

def to_7bit_string(some_basestring):
    return some_basestring.encode('utf-8') if isinstance(some_basestring, unicode) else some_basestring

class MailSender(object):
    
    def __init__(self, sender, password, SMTP_host, SMTP_port, use_TLS):
        self.sender = sender
        self.password = password
        self.SMTP_host = SMTP_host
        self.SMTP_port = SMTP_port
        self.use_TLS = use_TLS

    def wrap_as_attachment(self, stream, filename, mime_type):
        result = MIMEBase(*mime_type.split('/'))
        result.set_payload(stream.read())
        encoders.encode_base64(result)
        result.add_header('Content-Disposition', 'attachment', filename=filename)
        return result
    
    def get_server(self):
        server = smtplib.SMTP('%s:%d' % (self.SMTP_host, self.SMTP_port))
        if self.use_TLS:
            server.starttls()
        if self.password:
            server.login(self.sender, self.password)
        return server

    def send_mail(self, to, subject, message, *attachments):
        if isinstance(to, basestring):
            to = (to,)
        message = MIMEText(to_7bit_string(message), 'plain', 'utf-8')
        if attachments:
            msg = MIMEMultipart()
            msg.attach(message)
            for a in attachments:
                msg.attach(a)
            message = msg
        message['Subject'] = subject
        message['From'] = self.sender
        message['To'] = u', '.join(to)
        server = self.get_server()
        server.sendmail(self.sender, to, message.as_string())
        server.quit()

            
            
