
We should refactor the list display for newsbrowser and knowledgebrowser, since they are essentially doing te same.
It should be on its own as document_list_widget.py
Each item will consist of the title in bold
and in the second line  a sequence of tags (icons or emojis) to mark the 
-- source (medrxiv", "pubmed", "other"), 
-- an optional  "recommended" emoji, 
-- an optional tag for personal bookmark and/or project bookmark
-- publication date (or year, if date not available, else ''), Authors (trimed to max 25 char then ...)

We should refactor the way how we display documentss in various modules too (knowledgebrowser, newsbrowser) -> into its own file document_display_widget.py
It is a tabbed interface, showing one or more document aspects
tabs can be "summary_display_widget", "abstract_display_widget", "pdf_display_widget" (and in the future others)
unless as stated in the constructor parameter, the widget will display 
-- the summary (if available - else a button should be there allowing to create the summary), 
-- the abstract (if available, else the widget shoud try and fetch the website by doi or other urls saved in the document details and display it), 
-- then the pdf (if available: in the future, we wil have a function fetch_pdf, so there shoudld be buttons "fetch"  and "upload" if no pdf is available, but for now inactive ). 
The sequence will be made user configurable in the fututure, for now we will use this default sequence.
Below the scrolled display, there are thumbs up/down icons for user rating, and boomark tick boxes for user and/or project bookmarking.
With all signal.slots, mind that there might be several isntances of the document display used simultaneously, displaying different documents in various modules of the app

For documents displayed in the newsbrowser, the user should be able to select between "suggested", "bookmarked", "pubmed", "medrxiv", "all"
Next to the selector widget, there should be a max results input, defaulting to 25
in newsbrowser, the flow of documents should be by default:
1) load all documents that are listed in the table reading_suggestions.document_id (foreign key to table documents)  and display them.
2) if the user selects "newest from pubmed", display the max_documents most recent (by publication date) documents with source pubmed, order by newest first
3) if the user selects "newest from medrxiv", then the same for medrxiv
4) for all, we combine the 4 above, but still stick to max_results in total, order by publication date

-  when displaying a document, try and display the summary with rating etc. If not available, display the abstract and offer a button to create the summary from it.
