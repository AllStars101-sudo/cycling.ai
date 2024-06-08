// script.js
window.onload = function() {
    const qrCodeImage = document.getElementById('qrCodeImage');
    const userName = document.getElementById('userName');
    const userId = document.getElementById('userId');
    const linkingTime = document.getElementById('linkingTime');
  
    // Retrieve the QR code URL and user information from the query parameters
    const urlParams = new URLSearchParams(window.location.search);
    const qrCodeUrl = urlParams.get('qrCodeUrl');
    const userNameValue = urlParams.get('userName');
    const userIdValue = urlParams.get('userId');
  
    // Set the QR code image source
    qrCodeImage.src = qrCodeUrl;
  
    // Set the user name and user ID
    userName.textContent = userNameValue;
    userId.textContent = userIdValue;
  
    // Set the linking time
    const currentTime = new Date().toLocaleString();
    linkingTime.textContent = currentTime;
  };