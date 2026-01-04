// AI4Scribe Helper - content.js

document.addEventListener('click', function (event) {
    // Check if CTRL key (or Command key on Mac) is pressed
    if (event.ctrlKey || event.metaKey) {

        let target = event.target;
        let eventTitle = "";

        // Strategy: Traverse up to find the main event container (role="button" or specific classes)
        // Then try to extract information.

        let foundTitle = "";

        // 1. Try to find immediate text
        if (target.innerText && target.innerText.trim().length > 0) {
            foundTitle = target.innerText;
        }

        // 2. Fallback: Check parent if immediate text is empty
        if (!foundTitle && target.parentElement && target.parentElement.innerText) {
            foundTitle = target.parentElement.innerText;
        }

        if (foundTitle) {
            // Replace newlines with space to handle multiline titles
            // We do NOT remove time patterns anymore to prevent accidental truncation.
            eventTitle = foundTitle.replace(/\n/g, " ").trim();
        }

        if (eventTitle) {
            console.log("AI4Scribe Detected Event:", eventTitle);
            // Debugging alert to confirm what text is captured
            // alert("AI4Scribe가 감지한 제목: " + eventTitle); 

            const baseUrl = "http://127.0.0.1:8000";
            const targetUrl = `${baseUrl}?auto_title=${encodeURIComponent(eventTitle)}`;

            window.open(targetUrl, '_blank');

            event.preventDefault();
            event.stopPropagation();
        } else {
            console.log("AI4Scribe: No text found in clicked element.");
        }
    }
}, true); // Use capture phase
