# Landing page copy (HOME, ABOUT, STORE)
Use this in Wix if your teacher requires a Wix page, or keep it as the text for the Bulletin site.

This copy is already live on the three welcome screens of the site: HOME is screen 1 (with the explainer video), ABOUT is screen 2 (About us), and STORE is screen 3 (Get started). The code is the `SL` list in `index.html`. The school waitlist is built as a small form inside the app (see STORE below); it needs `supabase/admin.sql` to be run once in Supabase before it works.

There is no way to skip the quiz. The only way out of the welcome screens is the Take the quiz button (people who already finished the quiz, and organizers and admins, see Go to my Home instead). The steps after the welcome screens are at the bottom of this file.

## HOME
Headline: Find your thing.
Sub: Take a two-minute quiz and Bulletin ranks every club, volunteer spot and program at your school by how well it fits you.
[Explainer video goes here]
Button: Take the quiz (the corner button on every welcome screen goes to the next screen: About us, then Get started)
Three points: One place for everything / Matched to you / Free for students

## ABOUT
Mission: Helping students find clubs, volunteering and programs that fit them, so nobody misses out on something they would love just because they never heard about it.
Story: Bulletin started with a student at The Village School in Houston who noticed that great clubs were hard to find. It began as a Google Form quiz, got feedback from classmates, and grew into a website.
How it works: 1. Take the quiz in your own words. 2. See a match level from 1 to 10 for every opportunity. 3. Tap Explore, save, and join.
Who it is for: Middle school, high school and college students, and the clubs and organizations that want to meet them.

## STORE (Bulletin is free, so this is the "Get started" page)
Headline: Free for students. Always.
Sub: N school clubs and teams, N Houston opportunities and N online programs are waiting. Take the quiz and Bulletin ranks them for you. (The numbers are counted from the data.)
Small text: Takes about 2 minutes.
Steps: 1. Make a free account. 2. Take the quiz in your own words. 3. See a match level from 1 to 10 for every opportunity.
Plan: Students: Free, always. Take the quiz, save favorites, message organizers.
Coming soon: Schools and organizations: post and manage listings, approvals, sign-up reports. Join the waitlist.
Link in the Schools and organizations row: Join the waitlist →  (opens the form below; it is also in Settings > More as "School waitlist")
Button (bottom of the screen): Take the quiz →

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
