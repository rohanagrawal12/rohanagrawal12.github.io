# Landing page copy (HOME, ABOUT, STORE)
Use this in Wix if your teacher requires a Wix page, or keep it as the text for the Bulletin site.

This copy is already live on the three welcome screens of the site: HOME is screen 1 (with the explainer video), ABOUT is screen 2 (About us), and STORE is screen 3 (Get started). Each screen is a tall page that scrolls, made of bands (full-width sections), and a bar at the bottom of the screen always shows the three dots, Back and the next button. The code is the `slHome`, `slAbout` and `slStart` functions in `index.html`. The pictures of the app on these pages are real screenshots made by `tools/screens/make_screens.py` (the student "Alex" in them is made up). The school waitlist is built as a small form inside the app (see STORE below); it needs `supabase/admin.sql` to be run once in Supabase before it works.

There is no way to skip the quiz. The only way out of the welcome screens is the Take the quiz button (people who already finished the quiz, and organizers and admins, see Go to my Home instead). The steps after the welcome screens are at the bottom of this file.

## HOME
Small label: STARTING AT THE VILLAGE SCHOOL
Headline: Find your thing.
Sub: Take a two-minute quiz and Bulletin ranks every club, volunteer spot and program at your school by how well it fits you.
Button: Take the quiz
Small line: Free for students. No payment details needed.
Pictures: two real screenshots, the Home screen and the School list.
Band 2 (white), label WHY BULLETIN, headline "Less searching. More joining.", three cards:
- One place for everything: School clubs, Houston volunteering and online programs are in one list, not spread across flyers and group chats.
- Matched to you: Write a few sentences about yourself. Every opportunity gets a match level from 1 to 10.
- Free for students: Make an account, take the quiz and save what you like. It costs students nothing.
Band 3 (black), label THE EXPLAINER, headline "Watch how it works.", sub "The quiz, the match levels, Explore and saving, in one short video." [Explainer video goes here]
Footer (on every page): Find your thing. Made by a student in Houston, Texas.
(The corner button on every welcome screen is Log in. The next button at the bottom goes to the next screen: About us, then Get started.)

## ABOUT
Label: ABOUT US
Headline: Built by a student, for students.
Story: Bulletin started with a student at The Village School in Houston who noticed that great clubs were hard to find. It began as a Google Form quiz, got feedback from classmates, and grew into a website.
How it got built (label HOW IT GOT BUILT, headline "From a Google Form to a website."):
1. A Google Form quiz: It started as a quiz about what students like.
2. Feedback from 8 classmates: Most of them liked the phone design and the quiz.
3. A redesign: A shorter quiz, a simpler list, dark mode and a new name and logo.
4. A working website: It ranks 157 opportunities for you and saves what you like in your account. (The number is counted from the data.)
Problems and what changed: "The quiz was too long." It was shortened. / "The first name was already used by other student programs." It became Bulletin. / "The first design felt too busy." It was simplified.
Mission (very large type on a white band, with a red full stop; also at the bottom of the Home page inside the app): Helping students find clubs, volunteering and programs that fit them, so nobody misses out on something they would love just because they never heard about it.
(In the code it is the `MISSION` constant in `index.html`.)
Who it is for (label WHO IT IS FOR, headline "Students, and the people who help them."): Middle school, high school and college students, and the clubs and organizations that want to meet them. Four boxes: Students (Take the quiz and get matches.) / Parents and guardians (Answer the quiz about your child.) / Teachers and counselors (Answer the quiz about a student you are helping.) / Clubs and organizations (Coming soon: post opportunities for students to find.)

## STORE (Bulletin is free, so this is the "Get started" page)
Label: GET STARTED
Headline: Free for students. Always.
Sub: Every club, volunteer spot and program on Bulletin is free to look through. Take the quiz and Bulletin ranks them for you.
Small text: Takes about 2 minutes.
Three big numbers (counted from the data): 98 school clubs and teams / 31 Houston opportunities / 28 online programs
How it works (headline "Three steps. About two minutes."), each step with a real screenshot:
1. Make a free account. Your name, an email and a password. Nothing to pay. (picture: the Create your account form)
2. Take the quiz in your own words. Four short pages. Write like you’re talking to a friend: a sentence or two is plenty. (picture: the quiz)
3. See a match level from 1 to 10 for every opportunity. Clubs, volunteering and programs, best matches first. Save the ones you like. (picture: the School list)
Plans (headline "Students never pay."): Students, FREE: Take the quiz, save favorites, message organizers. / Schools and organizations, COMING SOON: Post and manage listings, approvals, sign-up reports. Join the waitlist →  (opens the form below; it is also in Settings > More as "School waitlist")
Red sign-up block: "Ready to find your thing?" / Make a free account, take the quiz and see your matches in about two minutes. Buttons: Create a free account (opens the sign-up form) and the link I already have an account. (Someone logged in who still owes the quiz sees "One last step." and Take the quiz. Someone who can already get in sees "Welcome back." and Go to my Home.)
Button (bottom of the screen, always there): Take the quiz →

## WAITLIST FORM (opens from the link above)
Title: Join the school waitlist
Sub: For schools, clubs and organizations that want to list their opportunities on Bulletin. We’ll email you when it’s ready. It’s free to join.
Boxes: School or organization / Your email / Anything you want us to know? (optional)
Button: Join the waitlist
Small print: We save your answers so we can reach you about Bulletin for schools.
Thank-you: You’re on the list. Thanks. We’ll email the address you gave when Bulletin is ready for schools and organizations.

## AFTER THE WELCOME SCREENS
Step 1, the account step: STEP 1 OF 2 / First, make a free account. / Then you’ll take a 2-minute quiz and Bulletin will match you with clubs and programs. Or look around as a guest.
Buttons: Create an account with email / Continue as a guest / I already have an account (Google and Microsoft are shown as coming soon).

Create your account: Full name, Email, Password, then "Who is this account for?" with four cards:
- I’m a student: Find clubs, volunteering and programs for yourself. You take a 2-minute quiz about you and get matches.
- I’m a parent or guardian: Find opportunities for your child. You answer the quiz about your child, and the matches are for them.
- I’m a teacher, counselor or professor: Help students find opportunities. You answer the quiz about a student you’re helping.
- I run a club, program or organization: Post opportunities for students to find. Organizers don’t take the quiz. (This one also asks for the organization name.)

Step 2, the quiz step: YOU’RE IN. ONE LAST STEP / Take the quiz to see your matches. (Parents: Take the quiz about your child. Teachers: Take the quiz about the student.) / Nothing is matched to you yet. Answer a few questions (about 2 minutes) and Bulletin puts the best clubs and programs first. There are no wrong answers. Button: Take the quiz →
A new account always starts empty: nothing is matched until its owner takes the quiz. Organizers and admins go straight to Home.

The quiz has four pages. Page 1 asks grade, school, ZIP code (5 digits) and an optional boy or girl question. The ZIP code is how Bulletin knows whether the Houston community list applies; the school clubs are for The Village School only. Anyone else still gets Explore (online and national programs) and a plain message on School or Community.

Home (the first screen after the quiz or a log in, and where the logo and the word “bulletin” always go): a summary of the whole app. For students, parents and teachers: counts of Saved, I’m doing, Messages and Friends, the top three matches in At your school, Near you and Online and national, Coming up (dates), and a short Saved list. For organizers: their listings, a Post an opportunity button and shortcuts to what students see.
