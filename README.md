# Facility Booking Bot - Venue and Role Summary  

## Venues and Their Permissions  

### 1. **Reading Room**  
- **Roles with Access** (in hierarchical order):  
    - **JCRC (Welfare D)**:  
        - Can approve or reject pending booking requests.  
        - Can view ALL bookings for this venue by ANYONE.  
        - Can cancel ANY bookings for this venue by ANYONE.
        - Can instantly book the venue. 
        - Can edit their bookings to this venue. 
    - **JCRC (Others)**:  
        - Can instantly book the venue. 
        - Can edit their bookings to this venue. 
        - Can cancel their bookings.
        - Can view their own bookings to this venue.
    - **Everyone Else**:  
        - Can request bookings, which require approval from JCRC (Welfare D).  
        - Can cancel their bookings.
        - Can view their own bookings to this venue.

---

### 2. **Dining Hall**  
- **Roles with Access** (in hierarchical order):  
    - **JCRC (Welfare D)**:  
        - Can approve or reject pending booking requests.  
        - Can view ALL bookings for this venue by ANYONE.  
        - Can cancel ANY bookings for this venue by ANYONE.
        - Can instantly book the venue. 
        - Can edit their bookings to this venue. 
    - **JCRC (Others)**:  
        - Can instantly book the venue. 
        - Can edit their bookings to this venue. 
        - Can cancel their bookings.
        - Can view their own bookings to this venue.
    - **Everyone Else**:  
        - Can request bookings, which require approval from JCRC (Welfare D).  
        - Can cancel their bookings.
        - Can view their own bookings to this venue.

---

### 3. **MPSH**  
- **Roles with Access** (in hierarchical order):  
    - **JCRC (Sports D and Culture D)**:  
        - Can view ALL bookings for this venue by ANYONE.  
        - Can cancel ANY bookings for this venue by ANYONE.
        - Can instantly book the venue.  
        - Can use the `/mass_book` feature for bulk bookings.  
        - Can edit their bookings to this venue.  
    - **All Captains and Chair (Dance)**:  
        - Can instantly book the venue.  
        - Can use the `/mass_book` feature for bulk bookings.  
        - Can edit their bookings to this venue.  
        - Can cancel their bookings.
        - Can view their own bookings to this venue.

---

### 4. **Band Room**  
- **Roles with Access** (in hierarchical order):  
    - **Chairmen of Rockers and Inspire**:  
        - Can instantly book the venue.  
        - Can edit their bookings.
        - Can cancel their bookings.
        - Can view their own bookings to this venue.

---

### 5. **Block Lounges (A Blk Lounge, B Blk Lounge, etc.)**  
- **Roles with Access** (in hierarchical order):  
    - **Block Heads**:  
        - Can approve or reject booking requests for their block's lounge. 
        - Can view ALL bookings for their block's lounge by ANYONE.  
        - Can cancel ANY bookings for their block's lounge by ANYONE.
        - Can instantly book their own block's lounge.   
        - Can edit their bookings.  
    - **Everyone Else**:  
        - Can request bookings, which require approval from their Block Head. 
        - Can cancel their bookings.
        - Can view their own bookings to this venue.  

---

## Roles and Their Permissions  

### 1. **Admin**  
- **Permissions**:  
    - Can view and cancel all bookings across all venues.  
    - Can update user roles and CCAs.  
    - Can restart the bot.  

- **Functions Available**:  
    - `/admin_update`: Update user roles and CCAs.  
    - `/restart`: Restart the bot.  
    - `/view`: View all bookings.  
    - `/cancel`: Cancel any booking.  

---

### 2. **JCRC (Welfare D)**  
- **Permissions**:  
    - Can instantly book Reading Room and Dining Hall.  
    - Can approve or reject bookings for Reading Room and Dining Hall.  
    - Can view ALL bookings for Reading Room and Dining Hall by ANYONE.  
    - Can cancel ANY bookings for Reading Room and Dining Hall by ANYONE.  
    - Can edit their own bookings for Reading Room and Dining Hall.  

- **Functions Available**:  
    - `/book`: Start a booking request.  
    - `/approve`: Approve or reject pending bookings for Reading Room and Dining Hall.  
    - `/view`: View all bookings for Reading Room and Dining Hall + their own bookings.  
    - `/cancel`: Cancel their own bookings + any Reading Room/Dining Hall bookings.  
    - `/edit`: Edit their own bookings for Reading Room and Dining Hall.  
    - `/getid`: Get Telegram ID.  

---

### 3. **JCRC (Others)**  
- **Permissions**:  
    - Can instantly book Reading Room and Dining Hall.  
    - Can edit their own bookings for Reading Room and Dining Hall.  
    - Can cancel their own bookings.  
    - Can view their own bookings.  

- **Functions Available**:  
    - `/book`: Start a booking request.  
    - `/view`: View their own bookings.  
    - `/cancel`: Cancel their own bookings.  
    - `/edit`: Edit their own bookings for Reading Room and Dining Hall.  
    - `/getid`: Get Telegram ID.  

---

### 4. **JCRC (Sports D and Culture D)**  
- **Permissions**: 
    - All permissions above from JCRC (Others).
    - Can instantly book MPSH.  
    - Can view ALL bookings for MPSH by ANYONE.  
    - Can cancel ANY bookings for MPSH by ANYONE.  
    - Can use the `/mass_book` feature for bulk MPSH bookings.  
    - Can edit their own bookings for MPSH.  

- **Functions Available**:  
    - `/book`: Start a booking request.  
    - `/mass_book`: Submit multiple MPSH bookings at once.  
    - `/view`: View all MPSH bookings + their own bookings.  
    - `/cancel`: Cancel their own bookings + any MPSH bookings.  
    - `/edit`: Edit their own bookings for Reading Room, Dining Hall, and MPSH.  
    - `/getid`: Get Telegram ID.  

---

### 5. **Captains (All CCAs)**  
- **Permissions**:  
    - Can instantly book MPSH.  
    - Can use the `/mass_book` feature for bulk MPSH bookings.  
    - Can edit their own MPSH bookings.  
    - Can cancel their own bookings.  
    - Can view their own bookings.  

- **Functions Available**:  
    - `/book`: Start a booking request.  
    - `/mass_book`: Submit multiple MPSH bookings at once.  
    - `/edit`: Edit their own MPSH bookings.  
    - `/view`: View their own bookings.  
    - `/cancel`: Cancel their own bookings.  
    - `/getid`: Get Telegram ID.  

---

### 6. **Chairman (Dance)**  
- **Permissions**:  
    - Can instantly book MPSH.  
    - Can use the `/mass_book` feature for bulk MPSH bookings.  
    - Can edit their own MPSH bookings.  
    - Can cancel their own bookings.  
    - Can view their own bookings.  

- **Functions Available**:  
    - `/book`: Start a booking request.  
    - `/mass_book`: Submit multiple MPSH bookings at once.  
    - `/edit`: Edit their own MPSH bookings.  
    - `/view`: View their own bookings.  
    - `/cancel`: Cancel their own bookings.  
    - `/getid`: Get Telegram ID.  

---

### 7. **Chairman (Rockers and Inspire)**  
- **Permissions**:  
    - Can instantly book Band Room.  
    - Can edit their own Band Room bookings.  
    - Can cancel their own bookings.  
    - Can view their own bookings.  

- **Functions Available**:  
    - `/book`: Start a booking request.  
    - `/edit`: Edit their own Band Room bookings.  
    - `/view`: View their own bookings.  
    - `/cancel`: Cancel their own bookings.  
    - `/getid`: Get Telegram ID.  

---

### 8. **Block Heads**  
- **Permissions**:  
    - Can instantly book their own block's lounge.  
    - Can approve or reject booking requests for their own block's lounge.  
    - Can view ALL bookings for their own block's lounge by ANYONE.  
    - Can cancel ANY bookings for their own block's lounge by ANYONE.  
    - Can edit their own bookings.  

- **Functions Available**:  
    - `/book`: Start a booking request.  
    - `/approve`: Approve or reject pending bookings for their block's lounge.  
    - `/edit`: Edit their own bookings.  
    - `/view`: View all bookings for their block's lounge + their own bookings.  
    - `/cancel`: Cancel their own bookings + any bookings for their block's lounge.  
    - `/getid`: Get Telegram ID.  

---

### 9. **Residents**  
- **Permissions**:  
    - Can request bookings for Reading Room, Dining Hall, and Block Lounges (requires approval).  
    - Can cancel their own bookings.  
    - Can view their own bookings only.  

- **Functions Available**:  
    - `/book`: Start a booking request (requires approval).  
    - `/view`: View their own bookings only.  
    - `/cancel`: Cancel their own bookings only.  
    - `/getid`: Get Telegram ID.  

---
