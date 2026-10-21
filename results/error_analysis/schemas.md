# Schemas of the sampled dev databases

## battle_death

```sql
CREATE TABLE "battle" (
"id" int,
"name" text,
"date" text,
"bulgarian_commander" text,
"latin_commander" text,
"result" text,
primary key("id")
);

CREATE TABLE "ship" (
"lost_in_battle" int,
"id" int,
"name" text,
"tonnage" text,
"ship_type" text,
"location" text,
"disposition_of_ship" text,
primary key("id"),
foreign key (`lost_in_battle`) references `battle`("id")
);

CREATE TABLE "death" (
"caused_by_ship_id" int,
"id" int,
"note" text,
"killed" int,
"injured" int,
primary key("id"),
foreign key ("caused_by_ship_id") references `ship`("id")
);
```

## car_1

```sql
CREATE TABLE "continents" (
	"ContId" INTEGER PRIMARY KEY,
	"Continent" TEXT
);

CREATE TABLE "countries" (
	"CountryId" INTEGER PRIMARY KEY,
	"CountryName" TEXT,
	"Continent" INTEGER,
	FOREIGN KEY (Continent) REFERENCES continents(ContId)
);

CREATE TABLE "car_makers" (
	"Id" INTEGER PRIMARY KEY,
	"Maker" TEXT,
	"FullName" TEXT,
	"Country" TEXT,
	FOREIGN KEY (Country) REFERENCES countries(CountryId)
);

CREATE TABLE "model_list" (
	"ModelId" INTEGER PRIMARY KEY,
	"Maker" INTEGER,
	"Model" TEXT UNIQUE,
	FOREIGN KEY (Maker) REFERENCES car_makers (Id)

);

CREATE TABLE "car_names" (
	"MakeId" INTEGER PRIMARY KEY,
	"Model" TEXT,
	"Make" TEXT,
	FOREIGN KEY (Model) REFERENCES model_list (Model)
);

CREATE TABLE "cars_data" (
	"Id" INTEGER PRIMARY KEY,
	"MPG" TEXT,
	"Cylinders" INTEGER,
	"Edispl" REAL,
	"Horsepower" TEXT,
	"Weight" INTEGER,
	"Accelerate" REAL,
	"Year" INTEGER,
	FOREIGN KEY (Id) REFERENCES car_names (MakeId)
);
```

## concert_singer

```sql
CREATE TABLE "stadium" (
"Stadium_ID" int,
"Location" text,
"Name" text,
"Capacity" int,
"Highest" int,
"Lowest" int,
"Average" int,
PRIMARY KEY ("Stadium_ID")
);

CREATE TABLE "singer" (
"Singer_ID" int,
"Name" text,
"Country" text,
"Song_Name" text,
"Song_release_year" text,
"Age" int,
"Is_male" bool,
PRIMARY KEY ("Singer_ID")
);

CREATE TABLE "concert" (
"concert_ID" int,
"concert_Name" text,
"Theme" text,
"Stadium_ID" text,
"Year" text,
PRIMARY KEY ("concert_ID"),
FOREIGN KEY ("Stadium_ID") REFERENCES "stadium"("Stadium_ID")
);

CREATE TABLE "singer_in_concert" (
"concert_ID" int,
"Singer_ID" text,
PRIMARY KEY ("concert_ID","Singer_ID"),
FOREIGN KEY ("concert_ID") REFERENCES "concert"("concert_ID"),
FOREIGN KEY ("Singer_ID") REFERENCES "singer"("Singer_ID")
);
```

## course_teach

```sql
CREATE TABLE "course" (
"Course_ID" int,
"Staring_Date" text,
"Course" text,
PRIMARY KEY ("Course_ID")
);

CREATE TABLE "teacher" (
"Teacher_ID" int,
"Name" text,
"Age" text,
"Hometown" text,
PRIMARY KEY ("Teacher_ID")
);

CREATE TABLE "course_arrange" (
"Course_ID" int,
"Teacher_ID" int,
"Grade" int,
PRIMARY KEY ("Course_ID","Teacher_ID","Grade"),
FOREIGN KEY ("Course_ID") REFERENCES `course`("Course_ID"),
FOREIGN KEY ("Teacher_ID") REFERENCES `teacher`("Teacher_ID")
);
```

## cre_Doc_Template_Mgt

```sql
CREATE TABLE Ref_Template_Types (
Template_Type_Code CHAR(15) NOT NULL,
Template_Type_Description VARCHAR(255) NOT NULL,
PRIMARY KEY (Template_Type_Code)
);

CREATE TABLE Templates (
Template_ID INTEGER NOT NULL,
Version_Number INTEGER NOT NULL,
Template_Type_Code CHAR(15) NOT NULL,
Date_Effective_From DATETIME,
Date_Effective_To DATETIME,
Template_Details VARCHAR(255) NOT NULL,
PRIMARY KEY (Template_ID),
FOREIGN KEY (Template_Type_Code) REFERENCES Ref_Template_Types (Template_Type_Code)
);

CREATE TABLE Documents (
Document_ID INTEGER NOT NULL,
Template_ID INTEGER,
Document_Name VARCHAR(255),
Document_Description VARCHAR(255),
Other_Details VARCHAR(255),
PRIMARY KEY (Document_ID),
FOREIGN KEY (Template_ID) REFERENCES Templates (Template_ID)
);

CREATE TABLE Paragraphs (
Paragraph_ID INTEGER NOT NULL,
Document_ID INTEGER NOT NULL,
Paragraph_Text VARCHAR(255),
Other_Details VARCHAR(255),
PRIMARY KEY (Paragraph_ID),
FOREIGN KEY (Document_ID) REFERENCES Documents (Document_ID)
);
```

## dog_kennels

```sql
CREATE TABLE `Breeds` (
`breed_code` VARCHAR(10) PRIMARY KEY ,
`breed_name` VARCHAR(80)
);

CREATE TABLE `Charges` (
`charge_id` INTEGER PRIMARY KEY ,
`charge_type` VARCHAR(10),
`charge_amount` DECIMAL(19,4)
);

CREATE TABLE `Sizes` (
`size_code` VARCHAR(10) PRIMARY KEY ,
`size_description` VARCHAR(80)
);

CREATE TABLE `Treatment_Types` (
`treatment_type_code` VARCHAR(10) PRIMARY KEY ,
`treatment_type_description` VARCHAR(80)
);

CREATE TABLE `Owners` (
`owner_id` INTEGER PRIMARY KEY ,
`first_name` VARCHAR(50),
`last_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);

CREATE TABLE `Dogs` (
`dog_id` INTEGER PRIMARY KEY ,
`owner_id` INTEGER NOT NULL,
`abandoned_yn` VARCHAR(1),
`breed_code` VARCHAR(10) NOT NULL,
`size_code` VARCHAR(10) NOT NULL,
`name` VARCHAR(50),
`age` VARCHAR(20),
`date_of_birth` DATETIME,
`gender` VARCHAR(1),
`weight` VARCHAR(20),
`date_arrived` DATETIME,
`date_adopted` DATETIME,
`date_departed` DATETIME,
FOREIGN KEY (`breed_code` ) REFERENCES `Breeds`(`breed_code` ),
FOREIGN KEY (`size_code` ) REFERENCES `Sizes`(`size_code` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` ),
FOREIGN KEY (`owner_id` ) REFERENCES `Owners`(`owner_id` )
);

CREATE TABLE `Professionals` (
`professional_id` INTEGER PRIMARY KEY ,
`role_code` VARCHAR(10) NOT NULL,
`first_name` VARCHAR(50),
`street` VARCHAR(50),
`city` VARCHAR(50),
`state` VARCHAR(20),
`zip_code` VARCHAR(20),
`last_name` VARCHAR(50),
`email_address` VARCHAR(50),
`home_phone` VARCHAR(20),
`cell_number` VARCHAR(20)
);

CREATE TABLE `Treatments` (
`treatment_id` INTEGER PRIMARY KEY ,
`dog_id` INTEGER NOT NULL,
`professional_id` INTEGER NOT NULL,
`treatment_type_code` VARCHAR(10) NOT NULL,
`date_of_treatment` DATETIME,
`cost_of_treatment` DECIMAL(19,4),
FOREIGN KEY (`treatment_type_code` ) REFERENCES `Treatment_Types`(`treatment_type_code` ),
FOREIGN KEY (`professional_id` ) REFERENCES `Professionals`(`professional_id` ),
FOREIGN KEY (`dog_id` ) REFERENCES `Dogs`(`dog_id` )
);
```

## flight_2

```sql
CREATE TABLE 'airlines' (
	uid INTEGER PRIMARY KEY,
	Airline TEXT,
	Abbreviation TEXT,
	Country TEXT
);

CREATE TABLE 'airports' (
	City TEXT,
	AirportCode TEXT PRIMARY KEY,
	AirportName TEXT,
	Country TEXT,
	CountryAbbrev TEXT
);

CREATE TABLE 'flights' (
	Airline INTEGER,
	FlightNo INTEGER,
	SourceAirport TEXT,
	DestAirport TEXT,
	PRIMARY KEY(Airline, FlightNo),
	FOREIGN KEY (SourceAirport) REFERENCES airports(AirportCode),
	FOREIGN KEY (DestAirport) REFERENCES airports(AirportCode)
);
```

## museum_visit

```sql
CREATE TABLE "museum" (
"Museum_ID" int,
"Name" text,
"Num_of_Staff" int,
"Open_Year" text,
PRIMARY KEY ("Museum_ID")
);

CREATE TABLE "visitor" (
"ID" int,
"Name" text,
"Level_of_membership" int,
"Age" int,
PRIMARY KEY ("ID")
);

CREATE TABLE "visit" (
"Museum_ID" int,
"visitor_ID" text,
"Num_of_Ticket" int,
"Total_spent" real,
PRIMARY KEY ("Museum_ID","visitor_ID"),
FOREIGN KEY ("Museum_ID") REFERENCES `museum`("Museum_ID"),
FOREIGN KEY ("visitor_ID") REFERENCES `visitor`("ID")
);
```

## network_1

```sql
CREATE TABLE Highschooler(
	ID int primary key,
	name text,
	grade int);

CREATE TABLE Friend(
	student_id int,
	friend_id int,
	primary key (student_id,friend_id),
	foreign key(student_id) references Highschooler(ID),
	foreign key (friend_id) references Highschooler(ID)
);

CREATE TABLE Likes(
	student_id int,
	liked_id int,
	primary key (student_id, liked_id),
        foreign key (liked_id) references Highschooler(ID),
        foreign key (student_id) references Highschooler(ID)
);
```

## orchestra

```sql
CREATE TABLE "conductor" (
"Conductor_ID" int,
"Name" text,
"Age" int,
"Nationality" text,
"Year_of_Work" int,
PRIMARY KEY ("Conductor_ID")
);

CREATE TABLE "orchestra" (
"Orchestra_ID" int,
"Orchestra" text,
"Conductor_ID" int,
"Record_Company" text,
"Year_of_Founded" real,
"Major_Record_Format" text,
PRIMARY KEY ("Orchestra_ID"),
FOREIGN KEY (`Conductor_ID`) REFERENCES `conductor`(`Conductor_ID`)
);

CREATE TABLE "performance" (
"Performance_ID" int,
"Orchestra_ID" int,
"Type" text,
"Date" text,
"Official_ratings_(millions)" real,
"Weekly_rank" text,
"Share" text,
PRIMARY KEY ("Performance_ID"),
FOREIGN KEY (`Orchestra_ID`) REFERENCES `orchestra`(`Orchestra_ID`)
);

CREATE TABLE "show" (
"Show_ID" int,
"Performance_ID" int,
"If_first_show" bool,
"Result" text,
"Attendance" real,
FOREIGN KEY (`Performance_ID`) REFERENCES `performance`(`Performance_ID`)
);
```

## pets_1

```sql
CREATE TABLE Student (
       StuID    	INTEGER PRIMARY KEY,
       LName		VARCHAR(12),
       Fname		VARCHAR(12),
       Age		INTEGER,
       Sex		VARCHAR(1),
       Major		INTEGER,
       Advisor		INTEGER,
       city_code	VARCHAR(3)
);

CREATE TABLE Has_Pet (
       StuID		INTEGER,
       PetID		INTEGER,
       FOREIGN KEY(PetID) REFERENCES Pets(PetID),
       FOREIGN KEY(StuID) REFERENCES Student(StuID)
);

CREATE TABLE Pets (
       PetID		INTEGER PRIMARY KEY,
       PetType		VARCHAR(20),
       pet_age INTEGER,
       weight REAL
);
```

## poker_player

```sql
CREATE TABLE "poker_player" (
"Poker_Player_ID" int,
"People_ID" int,
"Final_Table_Made" real,
"Best_Finish" real,
"Money_Rank" real,
"Earnings" real,
PRIMARY KEY ("Poker_Player_ID"),
FOREIGN KEY ("People_ID") REFERENCES `people`("People_ID")
);

CREATE TABLE "people" (
"People_ID" int,
"Nationality" text,
"Name" text,
"Birth_Date" text,
"Height" real,
PRIMARY KEY ("People_ID")
);
```

## real_estate_properties

```sql
CREATE TABLE `Ref_Feature_Types` (
`feature_type_code` VARCHAR(20) PRIMARY KEY,
`feature_type_name` VARCHAR(80)
);

CREATE TABLE `Ref_Property_Types` (
`property_type_code` VARCHAR(20) PRIMARY KEY,
`property_type_description` VARCHAR(80)
);

CREATE TABLE `Other_Available_Features` (
`feature_id` INTEGER PRIMARY KEY,
`feature_type_code` VARCHAR(20) NOT NULL,
`feature_name` VARCHAR(80),
`feature_description` VARCHAR(80),
FOREIGN KEY (`feature_type_code` ) REFERENCES `Ref_Feature_Types`(`feature_type_code` )
);

CREATE TABLE `Properties` (
`property_id` INTEGER PRIMARY KEY,
`property_type_code` VARCHAR(20) NOT NULL,
`date_on_market` DATETIME,
`date_sold` DATETIME,
`property_name` VARCHAR(80),
`property_address` VARCHAR(255),
`room_count` INTEGER,
`vendor_requested_price` DECIMAL(19,4),
`buyer_offered_price` DECIMAL(19,4),
`agreed_selling_price` DECIMAL(19,4),
`apt_feature_1` VARCHAR(255),
`apt_feature_2` VARCHAR(255),
`apt_feature_3` VARCHAR(255),
`fld_feature_1` VARCHAR(255),
`fld_feature_2` VARCHAR(255),
`fld_feature_3` VARCHAR(255),
`hse_feature_1` VARCHAR(255),
`hse_feature_2` VARCHAR(255),
`hse_feature_3` VARCHAR(255),
`oth_feature_1` VARCHAR(255),
`oth_feature_2` VARCHAR(255),
`oth_feature_3` VARCHAR(255),
`shp_feature_1` VARCHAR(255),
`shp_feature_2` VARCHAR(255),
`shp_feature_3` VARCHAR(255),
`other_property_details` VARCHAR(255),
FOREIGN KEY (`property_type_code` ) REFERENCES `Ref_Property_Types`(`property_type_code` )
);

CREATE TABLE `Other_Property_Features` (
`property_id` INTEGER NOT NULL,
`feature_id` INTEGER NOT NULL,
`property_feature_description` VARCHAR(80),
FOREIGN KEY (`feature_id` ) REFERENCES `Other_Available_Features`(`feature_id` ),
FOREIGN KEY (`property_id` ) REFERENCES `Properties`(`property_id` )
);
```

## singer

```sql
CREATE TABLE "singer" (
"Singer_ID" int,
"Name" text,
"Birth_Year" real,
"Net_Worth_Millions" real,
"Citizenship" text,
PRIMARY KEY ("Singer_ID")
);

CREATE TABLE "song" (
"Song_ID" int,
"Title" text,
"Singer_ID" int,
"Sales" real,
"Highest_Position" real,
PRIMARY KEY ("Song_ID"),
FOREIGN KEY ("Singer_ID") REFERENCES `singer`("Singer_ID")
);
```

## student_transcripts_tracking

```sql
CREATE TABLE `Addresses` (
`address_id` INTEGER PRIMARY KEY,
`line_1` VARCHAR(255),
`line_2` VARCHAR(255),
`line_3` VARCHAR(255),
`city` VARCHAR(255),
`zip_postcode` VARCHAR(20),
`state_province_county` VARCHAR(255),
`country` VARCHAR(255),
`other_address_details` VARCHAR(255)
);

CREATE TABLE `Courses` (
`course_id` INTEGER PRIMARY KEY,
`course_name` VARCHAR(255),
`course_description` VARCHAR(255),
`other_details` VARCHAR(255)
);

CREATE TABLE `Departments` (
`department_id` INTEGER PRIMARY KEY,
`department_name` VARCHAR(255),
`department_description` VARCHAR(255),
`other_details` VARCHAR(255)
);

CREATE TABLE `Degree_Programs` (
`degree_program_id` INTEGER PRIMARY KEY,
`department_id` INTEGER NOT NULL,
`degree_summary_name` VARCHAR(255),
`degree_summary_description` VARCHAR(255),
`other_details` VARCHAR(255),
FOREIGN KEY (`department_id` ) REFERENCES `Departments`(`department_id` )
);

CREATE TABLE `Sections` (
`section_id` INTEGER PRIMARY KEY,
`course_id` INTEGER NOT NULL,
`section_name` VARCHAR(255),
`section_description` VARCHAR(255),
`other_details` VARCHAR(255),
FOREIGN KEY (`course_id` ) REFERENCES `Courses`(`course_id` )
);

CREATE TABLE `Semesters` (
`semester_id` INTEGER PRIMARY KEY,
`semester_name` VARCHAR(255),
`semester_description` VARCHAR(255),
`other_details` VARCHAR(255)
);

CREATE TABLE `Students` (
`student_id` INTEGER PRIMARY KEY,
`current_address_id` INTEGER NOT NULL,
`permanent_address_id` INTEGER NOT NULL,
`first_name` VARCHAR(80),
`middle_name` VARCHAR(40),
`last_name` VARCHAR(40),
`cell_mobile_number` VARCHAR(40),
`email_address` VARCHAR(40),
`ssn` VARCHAR(40),
`date_first_registered` DATETIME,
`date_left` DATETIME,
`other_student_details` VARCHAR(255),
FOREIGN KEY (`current_address_id` ) REFERENCES `Addresses`(`address_id` ),
FOREIGN KEY (`permanent_address_id` ) REFERENCES `Addresses`(`address_id` )
);

CREATE TABLE `Student_Enrolment` (
`student_enrolment_id` INTEGER PRIMARY KEY,
`degree_program_id` INTEGER NOT NULL,
`semester_id` INTEGER NOT NULL,
`student_id` INTEGER NOT NULL,
`other_details` VARCHAR(255),
FOREIGN KEY (`degree_program_id` ) REFERENCES `Degree_Programs`(`degree_program_id` ),
FOREIGN KEY (`semester_id` ) REFERENCES `Semesters`(`semester_id` ),
FOREIGN KEY (`student_id` ) REFERENCES `Students`(`student_id` )
);

CREATE TABLE `Student_Enrolment_Courses` (
`student_course_id` INTEGER PRIMARY KEY,
`course_id` INTEGER NOT NULL,
`student_enrolment_id` INTEGER NOT NULL,
FOREIGN KEY (`course_id` ) REFERENCES `Courses`(`course_id` ),
FOREIGN KEY (`student_enrolment_id` ) REFERENCES `Student_Enrolment`(`student_enrolment_id` )
);

CREATE TABLE `Transcripts` (
`transcript_id` INTEGER PRIMARY KEY,
`transcript_date` DATETIME,
`other_details` VARCHAR(255)
);

CREATE TABLE `Transcript_Contents` (
`student_course_id` INTEGER NOT NULL,
`transcript_id` INTEGER NOT NULL,
FOREIGN KEY (`student_course_id` ) REFERENCES `Student_Enrolment_Courses`(`student_course_id` ),
FOREIGN KEY (`transcript_id` ) REFERENCES `Transcripts`(`transcript_id` )
);
```

## tvshow

```sql
CREATE TABLE "TV_Channel" (
"id" text,
"series_name" text,
"Country" text,
"Language" text,
"Content" text,
"Pixel_aspect_ratio_PAR" text,
"Hight_definition_TV" text,
"Pay_per_view_PPV" text,
"Package_Option" text,
PRIMARY KEY ("id")
);

CREATE TABLE "TV_series" (
"id" real,
"Episode" text,
"Air_Date" text,
"Rating" text,
"Share" real,
"18_49_Rating_Share" text,
"Viewers_m" text,
"Weekly_Rank" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);

CREATE TABLE "Cartoon" (
"id" real,
"Title" text,
"Directed_by" text,
"Written_by" text,
"Original_air_date" text,
"Production_code" real,
"Channel" text,
PRIMARY KEY ("id"),
FOREIGN KEY (`Channel`) REFERENCES `TV_Channel`(`id`)
);
```

## world_1

```sql
CREATE TABLE `city` (
  `ID` integer NOT NULL PRIMARY KEY AUTOINCREMENT
,  `Name` char(35) NOT NULL DEFAULT ''
,  `CountryCode` char(3) NOT NULL DEFAULT ''
,  `District` char(20) NOT NULL DEFAULT ''
,  `Population` integer NOT NULL DEFAULT '0'
,  CONSTRAINT `city_ibfk_1` FOREIGN KEY (`CountryCode`) REFERENCES `country` (`Code`)
);

CREATE TABLE `country` (
  `Code` char(3) NOT NULL DEFAULT ''
,  `Name` char(52) NOT NULL DEFAULT ''
,  `Continent` text  NOT NULL DEFAULT 'Asia'
,  `Region` char(26) NOT NULL DEFAULT ''
,  `SurfaceArea` float(10,2) NOT NULL DEFAULT '0.00'
,  `IndepYear` integer DEFAULT NULL
,  `Population` integer NOT NULL DEFAULT '0'
,  `LifeExpectancy` float(3,1) DEFAULT NULL
,  `GNP` float(10,2) DEFAULT NULL
,  `GNPOld` float(10,2) DEFAULT NULL
,  `LocalName` char(45) NOT NULL DEFAULT ''
,  `GovernmentForm` char(45) NOT NULL DEFAULT ''
,  `HeadOfState` char(60) DEFAULT NULL
,  `Capital` integer DEFAULT NULL
,  `Code2` char(2) NOT NULL DEFAULT ''
,  PRIMARY KEY (`Code`)
);

CREATE TABLE `countrylanguage` (
  `CountryCode` char(3) NOT NULL DEFAULT ''
,  `Language` char(30) NOT NULL DEFAULT ''
,  `IsOfficial` text  NOT NULL DEFAULT 'F'
,  `Percentage` float(4,1) NOT NULL DEFAULT '0.0'
,  PRIMARY KEY (`CountryCode`,`Language`)
,  CONSTRAINT `countryLanguage_ibfk_1` FOREIGN KEY (`CountryCode`) REFERENCES `country` (`Code`)
);
```

## wta_1

```sql
CREATE TABLE players(
    "player_id" INT PRIMARY KEY,
    "first_name" TEXT,
    "last_name" TEXT,
    "hand" TEXT,
    "birth_date" DATE,
    "country_code" TEXT
);

CREATE TABLE matches(
  "best_of" INT,
  "draw_size" INT,
  "loser_age" FLOAT,
  "loser_entry" TEXT,
  "loser_hand" TEXT,
  "loser_ht" INT,
  "loser_id" INT,
  "loser_ioc" TEXT,
  "loser_name" TEXT,
  "loser_rank" INT,
  "loser_rank_points" INT,
  "loser_seed" INT,
  "match_num" INT,
  "minutes" INT,
  "round" TEXT,
  "score" TEXT,
  "surface" TEXT,
  "tourney_date" DATE,
  "tourney_id" TEXT,
  "tourney_level" TEXT,
  "tourney_name" TEXT,
  "winner_age" FLOAT,
  "winner_entry" TEXT,
  "winner_hand" TEXT,
  "winner_ht" INT,
  "winner_id" INT,
  "winner_ioc" TEXT,
  "winner_name" TEXT,
  "winner_rank" INT,
  "winner_rank_points" INT,
  "winner_seed" INT,
  "year" INT,
  FOREIGN KEY(loser_id) REFERENCES players(player_id),
  FOREIGN KEY(winner_id) REFERENCES players(player_id)
);

CREATE TABLE rankings("ranking_date" DATE,"ranking" INT,"player_id" INT,"ranking_points" INT,"tours" INT,FOREIGN KEY(player_id) REFERENCES players(player_id));
```
