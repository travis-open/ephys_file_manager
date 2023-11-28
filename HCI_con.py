from pywinauto.application import Application



HCI_app = Application(backend='uia')
HCI_app.start("C:\Program Files\HCImageLive\HCImageLive.exe").connect(title_re='.* Display$', timeout=10)
HCI_app.connect(title_re='.* Display$', timeout=10)
dlg = HCI_app.window(title_re='.* Display$')
#tree=dlg.print_control_identifiers(depth=5)
cap = dlg.child_window(title="Capture1", auto_id="413", control_type="Button").wrapper_object()
#cap.click()