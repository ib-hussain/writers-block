USE blogWriter;
-- CREATE TYPE gender_enum AS ENUM ('Female', 'Male');

CREATE TABLE IF NOT EXISTS BlogData (
    blogID INT AUTO_INCREMENT PRIMARY KEY,
    blogText TEXT NOT NULL ,
    keywords TEXT DEFAULT NULL 
);
-- 7 parts
CREATE TABLE IF NOT EXISTS PromptData (
    promptID INT AUTO_INCREMENT PRIMARY KEY,
    writing TEXT NOT NULL,
    intro TEXT NOT NULL ,
    final_cta TEXT NOT NULL ,
    FAQs TEXT NOT NULL ,
    business_description TEXT NOT NULL ,
    short_cta TEXT NOT NULL ,
);
CREATE TABLE IF NOT EXISTS BlogParts (
    blogID INT AUTO_INCREMENT PRIMARY KEY,
    intro TEXT NOT NULL ,
    final_cta TEXT NOT NULL ,
    FAQs TEXT NOT NULL ,
    business_description TEXT NOT NULL ,
    short_cta TEXT NOT NULL ,
    FOREIGN KEY (blogID) REFERENCES BlogData(blogID)
);


