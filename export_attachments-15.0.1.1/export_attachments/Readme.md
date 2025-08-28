# Export Attachments

In Odoo, We can export all fields but binary fields is very hard to download for many records at once. So planned to give a solution for that.

- This module helps you to download all attachments or any binary fields in that model at once.
    
## Menu and Configuration
    
- Menu in Settings -> Technical -> Export Attachments -> Export Attachments Action

![alt text](static/description/s1.png "Export Attachment Menu")

- Export Menu Tree View

![alt text](static/description/s2.png "Export Menu Tree View")

- Export Menu Form View

![alt text](static/description/s3.png "Export Menu Form View")

- Create Server Action

![alt text](static/description/s9.png "Create Server Action")

- View : Any Configured model -> Action -> Export Attachments

![alt text](static/description/s4.png "Configured model -> Action -> Export Attachments")

## Features
    
- If any model does not have an binary fields or they want to download related documents

![alt text](static/description/s5.png "If any model does not have an binary fields or they want to download related documents")

- Select Which binary fields you want to download

![alt text](static/description/s6.png "Select Which binary fields you want to download")

- Restrict Download attachments to assign allowes groups

![alt text](static/description/s7.png "Restrict Download attachments to assign allowes groups")

- Create Server Action / Update Server Action / Remove (Action -> Export Attachments) / Add (Action -> Export Attachments)

![alt text](static/description/s9.png "Configured model -> Action -> Export Attachments")

## Options

1) To download related all attachments, enable "Download all related documents from attachments"

![alt text](static/description/s8.png "Download all related documents from attachments")

2) To download specific binary field, fill fields

![alt text](static/description/s6.png "To download specific binary field, fill fields")

## Filename Details

![alt text](static/description/s10.png "Configured model -> Action -> Export Attachments")

## Videos

### Initial Setup
[![Initial Setup](http://img.youtube.com/vi/1Via3k99HRs/0.jpg)](http://www.youtube.com/watch?v=1Via3k99HRs)

### Export Test
[![Export Test](http://img.youtube.com/vi/XrILxLA8Ies/0.jpg)](http://www.youtube.com/watch?v=XrILxLA8Ies)

## For next upgrade 

- Bulk import attachments using file name: 
    
    `[<model>-<recordID>-<field_name>]<filename>`

    Ex:-

    `[hr_applicant-10-document]odoo_gold_partner_rgb.png`

    We can easily import multiple attachments at once !!! 
