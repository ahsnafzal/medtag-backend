from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string


class EmailHelper:
    def __init__(self):
        pass

    def send_reset_password_email(self, subject, reset_link, first_name,
                                  recipient):

        try:
            # img_source = f"{settings.BASE_URL}/media/profile_pictures/logo.png"


            context = {"name": first_name, "reset_link": reset_link,
                       "login_link": settings.LOGIN_URI, }

            html_content = render_to_string("forget_password.html", context)
            msg = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                bcc=recipient,
            )

            msg.content_subtype = "html"
            msg.send()
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False

    def contact_email(self, data):

        try:
            # img_source = f"{settings.BASE_URL}/media/profile_pictures/logo.png"
            context = {"first_name": data.get('first_name'), 'last_name':data.get('last_name'), 'email':data.get('email'), 'message':data.get('message'),}

            email = data.get('email')
            subject = "Thank You for Contacting Us - MedTag"
            html_content = render_to_string("contact.html", context)
            msg = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                bcc=[email],
            )

            msg.content_subtype = "html"
            msg.send()
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False

    def create_teacher_email(self, recepient, first_name, subject):
        try:
            img_source = f"{settings.BASE_URL}/media/profile_pictures/logo.png"
            context = {"name": first_name, "login_link": settings.LOGIN_URI,
                       "logo": img_source, "password":
                       settings.TEACHER_PASSWORD}

            html_content = render_to_string("email.html", context)
            msg = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                bcc=recepient,
            )

            msg.content_subtype = "html"
            msg.send()
            return True
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
